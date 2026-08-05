#!/usr/bin/env python3
"""Exact SHA-gated 4bpp palette-transfer search for Sakura Taisen 2 PBOOK assets.

The tool never emits a candidate asset unless every configured region gate and
whole-asset SHA-256 gate passes. It is designed for the B139 follow-up where
geometry and changed-byte counts are known but the historical multi-level
palette-transfer rule is not yet recovered.

No game data is bundled. Inputs are user-owned source assets, glyph masks and a
JSON job manifest containing offsets, dimensions and expected hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unpack_4bpp(data: bytes, pixel_count: int | None = None) -> list[int]:
    out: list[int] = []
    for value in data:
        out.extend((value >> 4, value & 0x0F))
    return out if pixel_count is None else out[:pixel_count]


def pack_4bpp(pixels: Sequence[int]) -> bytes:
    if any(not 0 <= p <= 15 for p in pixels):
        raise ValueError("4bpp pixel outside 0..15")
    padded = list(pixels)
    if len(padded) & 1:
        padded.append(0)
    return bytes((padded[i] << 4) | padded[i + 1] for i in range(0, len(padded), 2))


def changed_bytes(a: bytes, b: bytes) -> int:
    if len(a) != len(b):
        raise ValueError("length mismatch")
    return sum(x != y for x, y in zip(a, b))


def histogram(pixels: Sequence[int]) -> list[int]:
    result = [0] * 16
    for p in pixels:
        result[p] += 1
    return result


@dataclass(frozen=True)
class Region:
    name: str
    offset: int
    width: int
    height: int
    stride_pixels: int
    mask_path: Path
    expected_region_sha256: str | None
    expected_changed_bytes: int | None
    preserve_zero_mask: bool = True

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def packed_row_bytes(self) -> int:
        return (self.stride_pixels + 1) // 2

    @property
    def packed_length(self) -> int:
        return self.packed_row_bytes * self.height


@dataclass(frozen=True)
class Job:
    asset_name: str
    source_path: Path
    source_sha256: str
    target_sha256: str
    output_path: Path
    regions: tuple[Region, ...]


def read_region_pixels(asset: bytes, region: Region) -> list[int]:
    pixels: list[int] = []
    row_bytes = region.packed_row_bytes
    for y in range(region.height):
        start = region.offset + y * row_bytes
        row = unpack_4bpp(asset[start : start + row_bytes], region.stride_pixels)
        pixels.extend(row[: region.width])
    return pixels


def write_region_pixels(asset: bytearray, region: Region, pixels: Sequence[int]) -> None:
    if len(pixels) != region.pixel_count:
        raise ValueError(f"{region.name}: wrong pixel count")
    row_bytes = region.packed_row_bytes
    for y in range(region.height):
        start = region.offset + y * row_bytes
        original_row = unpack_4bpp(asset[start : start + row_bytes], region.stride_pixels)
        original_row[: region.width] = pixels[y * region.width : (y + 1) * region.width]
        asset[start : start + row_bytes] = pack_4bpp(original_row)


def load_mask(region: Region) -> list[int]:
    raw = region.mask_path.read_bytes()
    pixels = unpack_4bpp(raw, region.pixel_count)
    if len(pixels) != region.pixel_count:
        raise ValueError(f"{region.name}: mask is too short")
    return pixels


Transfer = Callable[[int, int], int]


def transfer_families(level_map: Sequence[int]) -> Iterator[tuple[str, Transfer]]:
    """Yield compact historical-looking mask/background transfer families.

    `mask` is a 4bpp Korean glyph coverage level and `background` is the
    existing PBOOK descriptor pixel. The level map allows non-linear glyph
    coverage remapping before compositing.
    """
    lm = tuple(level_map)

    def replace(mask: int, background: int) -> int:
        return background if mask == 0 else lm[mask]

    def maximum(mask: int, background: int) -> int:
        return max(background, lm[mask])

    def minimum(mask: int, background: int) -> int:
        return background if mask == 0 else min(background, lm[mask])

    def sat_add(mask: int, background: int) -> int:
        return min(15, background + lm[mask])

    def sat_sub(mask: int, background: int) -> int:
        return max(0, background - lm[mask])

    def add_wrap(mask: int, background: int) -> int:
        return (background + lm[mask]) & 15

    def xor(mask: int, background: int) -> int:
        return background ^ lm[mask]

    def screen(mask: int, background: int) -> int:
        m = lm[mask]
        return 15 - ((15 - background) * (15 - m) + 7) // 15

    def multiply(mask: int, background: int) -> int:
        return (background * lm[mask] + 7) // 15

    yield "replace", replace
    yield "max", maximum
    yield "min", minimum
    yield "sat_add", sat_add
    yield "sat_sub", sat_sub
    yield "add_wrap", add_wrap
    yield "xor", xor
    yield "screen", screen
    yield "multiply", multiply

    for numerator in range(1, 16):
        denominator = 15

        def lerp(mask: int, background: int, n: int = numerator, d: int = denominator) -> int:
            coverage = lm[mask]
            effective = (coverage * n + d // 2) // d
            return max(0, min(15, (background * (15 - effective) + lm[mask] * effective + 7) // 15))

        yield f"lerp_{numerator}_15", lerp


def level_maps(active_levels: Sequence[int], exhaustive_limit: int = 200000) -> Iterator[tuple[str, tuple[int, ...]]]:
    """Generate monotonic and selected non-linear 16-entry coverage maps."""
    active = sorted(set(active_levels) - {0})
    base = [0] * 16
    for i in range(16):
        base[i] = i
    yield "identity", tuple(base)

    for gamma_name, values in (
        ("binary15", [0] + [15] * 15),
        ("binary1", [0] + [1] * 15),
        ("double", [min(15, i * 2) for i in range(16)]),
        ("half", [(i + 1) // 2 for i in range(16)]),
        ("inverse", [0] + [16 - i for i in range(1, 16)]),
    ):
        yield gamma_name, tuple(values)

    # Most glyph masks use only a few coverage levels. Exhaustively enumerate
    # nondecreasing mappings only for levels that actually occur.
    if not active:
        return
    combinations = 1
    for _ in active:
        combinations *= 16
    if combinations > exhaustive_limit:
        # Quantized monotonic families retain broad search coverage safely.
        for steps in (2, 3, 4, 5, 8, 16):
            values = [0]
            for i in range(1, 16):
                values.append(round((steps - 1) * i / 15) * 15 // max(1, steps - 1))
            yield f"quantized_{steps}", tuple(values)
        return

    for mapped in itertools.combinations_with_replacement(range(16), len(active)):
        values = list(base)
        values[0] = 0
        for source, target in zip(active, mapped):
            values[source] = target
        yield "mono_" + "_".join(map(str, mapped)), tuple(values)


def apply_transfer(background: Sequence[int], mask: Sequence[int], fn: Transfer, preserve_zero: bool) -> list[int]:
    if len(background) != len(mask):
        raise ValueError("background/mask size mismatch")
    out: list[int] = []
    for bg, mk in zip(background, mask):
        out.append(bg if preserve_zero and mk == 0 else fn(mk, bg))
    return out


def parse_job(path: Path) -> Job:
    doc = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    regions = []
    for item in doc["regions"]:
        regions.append(
            Region(
                name=item["name"],
                offset=int(item["offset"], 0) if isinstance(item["offset"], str) else int(item["offset"]),
                width=int(item["width"]),
                height=int(item["height"]),
                stride_pixels=int(item.get("stride_pixels", item["width"])),
                mask_path=(root / item["mask_path"]).resolve(),
                expected_region_sha256=item.get("expected_region_sha256"),
                expected_changed_bytes=item.get("expected_changed_bytes"),
                preserve_zero_mask=bool(item.get("preserve_zero_mask", True)),
            )
        )
    return Job(
        asset_name=doc["asset_name"],
        source_path=(root / doc["source_path"]).resolve(),
        source_sha256=doc["source_sha256"].lower(),
        target_sha256=doc["target_sha256"].lower(),
        output_path=(root / doc.get("output_path", f"{doc['asset_name']}.exact.bin")).resolve(),
        regions=tuple(regions),
    )


def search(job: Job, max_candidates: int | None = None) -> dict[str, object]:
    source = job.source_path.read_bytes()
    actual_source_sha = sha256(source)
    if actual_source_sha != job.source_sha256:
        raise RuntimeError(f"source SHA mismatch: {actual_source_sha}")

    region_inputs = []
    active_levels: set[int] = set()
    for region in job.regions:
        background = read_region_pixels(source, region)
        mask = load_mask(region)
        active_levels.update(mask)
        region_inputs.append((region, background, mask))

    tested = 0
    changed_gate_hits = 0
    region_sha_hits = 0
    for map_name, mapping in level_maps(sorted(active_levels)):
        for family_name, fn in transfer_families(mapping):
            tested += 1
            if max_candidates is not None and tested > max_candidates:
                break
            candidate = bytearray(source)
            all_changed_pass = True
            all_region_sha_pass = True
            region_results = []
            for region, background, mask in region_inputs:
                pixels = apply_transfer(background, mask, fn, region.preserve_zero_mask)
                write_region_pixels(candidate, region, pixels)
                candidate_region = bytes(candidate[region.offset : region.offset + region.packed_length])
                original_region = source[region.offset : region.offset + region.packed_length]
                changed = changed_bytes(original_region, candidate_region)
                region_hash = sha256(candidate_region)
                if region.expected_changed_bytes is not None and changed != region.expected_changed_bytes:
                    all_changed_pass = False
                if region.expected_region_sha256 and region_hash != region.expected_region_sha256.lower():
                    all_region_sha_pass = False
                region_results.append({"name": region.name, "changed_bytes": changed, "sha256": region_hash})
            if all_changed_pass:
                changed_gate_hits += 1
            if all_changed_pass and all_region_sha_pass:
                region_sha_hits += 1
                whole_hash = sha256(candidate)
                if whole_hash == job.target_sha256:
                    job.output_path.parent.mkdir(parents=True, exist_ok=True)
                    job.output_path.write_bytes(candidate)
                    return {
                        "status": "PASS_EXACT_PBOOK_ASSET_RECOVERED",
                        "asset": job.asset_name,
                        "tested": tested,
                        "map": map_name,
                        "family": family_name,
                        "output": str(job.output_path),
                        "output_sha256": whole_hash,
                        "regions": region_results,
                    }
        if max_candidates is not None and tested > max_candidates:
            break

    return {
        "status": "NO_EXACT_HIT",
        "asset": job.asset_name,
        "tested": tested,
        "changed_gate_hits": changed_gate_hits,
        "region_sha_hits": region_sha_hits,
        "output_emitted": False,
    }


def selftest() -> dict[str, object]:
    width, height = 16, 8
    source_pixels = [(x + y) & 15 for y in range(height) for x in range(width)]
    mask_pixels = [0 if (x + y) % 4 == 0 else ((x * 3 + y * 5) % 5) for y in range(height) for x in range(width)]
    mapping = tuple([0, 3, 7, 11, 15] + list(range(5, 16)))
    family = dict(transfer_families(mapping))["screen"]
    expected_pixels = apply_transfer(source_pixels, mask_pixels, family, True)
    source = pack_4bpp(source_pixels)
    expected = pack_4bpp(expected_pixels)

    recovered = None
    tested = 0
    active = sorted(set(mask_pixels))
    for map_name, candidate_map in level_maps(active, exhaustive_limit=1000000):
        for family_name, fn in transfer_families(candidate_map):
            tested += 1
            candidate = pack_4bpp(apply_transfer(source_pixels, mask_pixels, fn, True))
            if candidate == expected:
                recovered = {"map": map_name, "family": family_name}
                break
        if recovered:
            break
    return {
        "status": "PASS" if recovered else "FAIL",
        "tested": tested,
        "source_sha256": sha256(source),
        "expected_sha256": sha256(expected),
        "recovered": recovered,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("search")
    run.add_argument("job", type=Path)
    run.add_argument("--max-candidates", type=int)
    sub.add_parser("selftest")
    args = parser.parse_args()

    result = selftest() if args.command == "selftest" else search(parse_job(args.job), args.max_candidates)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
