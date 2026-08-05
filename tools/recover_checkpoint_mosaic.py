#!/usr/bin/env python3
"""Recover an exact patch by mosaicing sectors from many historical checkpoints.

The trusted apply script is parsed as literals and is never executed. Different
B110/B117/B118/B124/B127/B130-style BINs or ZIPs may each contribute a subset
of the final target sectors. A raw sector is accepted only when its complete
SHA-256 equals the target hash in the manifest.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from recover_exact_patch_from_manifest import (
    apply,
    find_image,
    hash_bytes,
    hash_file,
    load_manifest,
    package,
)

CHUNK = 8 * 1024 * 1024


def collect_files(root: Path, excluded: Path) -> list[Path]:
    excluded = excluded.resolve()
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved == excluded or excluded in resolved.parents:
            continue
        result.append(path)
    return result


def payload_path(payloads: Path, lba: int) -> Path:
    return payloads / f"PATCHED_SECTOR_LBA{lba}.bin"


def wanted_by_hash(manifest: dict[str, Any]) -> dict[str, int]:
    wanted: dict[str, int] = {}
    for lba_text, item in manifest["sectors"].items():
        digest = item["patched_sha256"]
        lba = int(lba_text)
        if digest in wanted and wanted[digest] != lba:
            raise ValueError(f"target SHA reused by LBAs {wanted[digest]} and {lba}")
        wanted[digest] = lba
    return wanted


def accept_sector(
    sector: bytes,
    source: str,
    manifest: dict[str, Any],
    wanted: dict[str, int],
    payloads: Path,
    provenance: dict[str, dict[str, Any]],
) -> bool:
    if len(sector) != manifest["raw_sector"]:
        return False
    digest = hash_bytes(sector)
    lba = wanted.get(digest)
    if lba is None:
        return False
    target = payload_path(payloads, lba)
    if target.exists():
        if hash_file(target) != digest:
            raise RuntimeError(f"payload collision at LBA {lba}")
        provenance[str(lba)]["also_seen_in"].append(source)
        return False
    target.write_bytes(sector)
    item = manifest["sectors"][str(lba)]
    provenance[str(lba)] = {
        "lba": lba,
        "asset": item.get("asset", ""),
        "patched_sha256": digest,
        "primary_source": source,
        "also_seen_in": [],
    }
    return True


def missing_lbas(manifest: dict[str, Any], payloads: Path) -> list[int]:
    raw = manifest["raw_sector"]
    missing: list[int] = []
    for lba_text, item in manifest["sectors"].items():
        lba = int(lba_text)
        path = payload_path(payloads, lba)
        if not path.exists() or path.stat().st_size != raw or hash_file(path) != item["patched_sha256"]:
            missing.append(lba)
    return sorted(missing)


def scan_loose_sectors(
    paths: Iterable[Path],
    manifest: dict[str, Any],
    wanted: dict[str, int],
    payloads: Path,
    provenance: dict[str, dict[str, Any]],
) -> int:
    found = 0
    raw = manifest["raw_sector"]
    for path in paths:
        try:
            if path.stat().st_size != raw:
                continue
            sector = path.read_bytes()
        except OSError:
            continue
        found += int(accept_sector(sector, f"loose:{path}", manifest, wanted, payloads, provenance))
    return found


def scan_zip_sector_members(
    paths: Iterable[Path],
    manifest: dict[str, Any],
    wanted: dict[str, int],
    payloads: Path,
    provenance: dict[str, dict[str, Any]],
) -> int:
    found = 0
    raw = manifest["raw_sector"]
    for archive_path in paths:
        if archive_path.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.file_size != raw:
                        continue
                    sector = archive.read(info)
                    label = f"zip-sector:{archive_path}!{info.filename}"
                    found += int(accept_sector(sector, label, manifest, wanted, payloads, provenance))
        except (zipfile.BadZipFile, OSError, RuntimeError):
            continue
    return found


def scan_image(
    image: Path,
    label: str,
    manifest: dict[str, Any],
    wanted: dict[str, int],
    payloads: Path,
    provenance: dict[str, dict[str, Any]],
) -> int:
    found = 0
    raw = manifest["raw_sector"]
    with image.open("rb") as stream:
        for lba in missing_lbas(manifest, payloads):
            stream.seek(lba * raw)
            sector = stream.read(raw)
            found += int(accept_sector(sector, label, manifest, wanted, payloads, provenance))
    return found


def scan_loose_checkpoint_bins(
    paths: Iterable[Path],
    manifest: dict[str, Any],
    wanted: dict[str, int],
    payloads: Path,
    provenance: dict[str, dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    found = 0
    audited: list[dict[str, Any]] = []
    for path in paths:
        try:
            if path.suffix.lower() != ".bin" or path.stat().st_size != manifest["source_size"]:
                continue
            before = len(missing_lbas(manifest, payloads))
            got = scan_image(path, f"checkpoint-bin:{path}", manifest, wanted, payloads, provenance)
            after = len(missing_lbas(manifest, payloads))
            audited.append({"path": str(path), "recovered": got, "missing_before": before, "missing_after": after})
            found += got
            if after == 0:
                break
        except OSError:
            continue
    return found, audited


def scan_zip_checkpoint_bins(
    paths: Iterable[Path],
    manifest: dict[str, Any],
    wanted: dict[str, int],
    payloads: Path,
    provenance: dict[str, dict[str, Any]],
    temp: Path,
) -> tuple[int, list[dict[str, Any]]]:
    found = 0
    audited: list[dict[str, Any]] = []
    for archive_path in paths:
        if archive_path.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for index, info in enumerate(archive.infolist()):
                    if info.is_dir() or info.file_size != manifest["source_size"]:
                        continue
                    extracted = temp / f"checkpoint_{len(audited):04d}_{index:04d}.bin"
                    with archive.open(info) as source, extracted.open("wb") as target:
                        shutil.copyfileobj(source, target, CHUNK)
                    before = len(missing_lbas(manifest, payloads))
                    got = scan_image(
                        extracted,
                        f"checkpoint-zip:{archive_path}!{info.filename}",
                        manifest,
                        wanted,
                        payloads,
                        provenance,
                    )
                    after = len(missing_lbas(manifest, payloads))
                    audited.append({
                        "archive": str(archive_path),
                        "member": info.filename,
                        "recovered": got,
                        "missing_before": before,
                        "missing_after": after,
                    })
                    extracted.unlink(missing_ok=True)
                    found += got
                    if after == 0:
                        return found, audited
        except (zipfile.BadZipFile, OSError, RuntimeError):
            continue
    return found, audited


def coverage(manifest: dict[str, Any], payloads: Path) -> dict[str, Any]:
    totals = Counter()
    recovered = Counter()
    for lba_text, item in manifest["sectors"].items():
        asset = item.get("asset") or "UNKNOWN"
        totals[asset] += 1
        path = payload_path(payloads, int(lba_text))
        if path.exists() and hash_file(path) == item["patched_sha256"]:
            recovered[asset] += 1
    rows = [
        {
            "asset": asset,
            "recovered": recovered[asset],
            "total": totals[asset],
            "complete": recovered[asset] == totals[asset],
        }
        for asset in sorted(totals)
    ]
    return {
        "assets_complete": sum(int(row["complete"]) for row in rows),
        "assets_total": len(rows),
        "sectors_recovered": sum(recovered.values()),
        "sectors_total": sum(totals.values()),
        "assets": rows,
    }


def write_cue(bin_path: Path) -> Path:
    cue = bin_path.with_suffix(".cue")
    cue.write_bytes(
        (f'FILE "{bin_path.name}" BINARY\r\n'
         "  TRACK 01 MODE1/2352\r\n"
         "    INDEX 01 00:00:00\r\n").encode("ascii")
    )
    return cue


def recover_mosaic(script: Path, root: Path, output: Path) -> dict[str, Any]:
    manifest = load_manifest(script)
    output.mkdir(parents=True, exist_ok=True)
    payloads = output / "PATCH_SECTORS"
    payloads.mkdir(exist_ok=True)
    temp = output / "_TEMP"
    temp.mkdir(exist_ok=True)
    paths = collect_files(root, output)
    wanted = wanted_by_hash(manifest)
    provenance: dict[str, dict[str, Any]] = {}

    stages: dict[str, int] = {}
    stages["loose_sector_files"] = scan_loose_sectors(paths, manifest, wanted, payloads, provenance)
    stages["zip_sector_members"] = scan_zip_sector_members(paths, manifest, wanted, payloads, provenance)
    stages["loose_checkpoint_bins"], loose_audit = scan_loose_checkpoint_bins(
        paths, manifest, wanted, payloads, provenance
    )
    zip_audit: list[dict[str, Any]] = []
    if missing_lbas(manifest, payloads):
        stages["zip_checkpoint_bins"], zip_audit = scan_zip_checkpoint_bins(
            paths, manifest, wanted, payloads, provenance, temp
        )
    else:
        stages["zip_checkpoint_bins"] = 0

    missing = missing_lbas(manifest, payloads)
    result: dict[str, Any] = {
        "status": "BLOCKED_PATCH_BYTES_NOT_FOUND" if missing else "PASS_EXACT_SECTOR_MOSAIC_RECOVERED",
        "manifest_sector_count": manifest["sector_count"],
        "stage_recovery_counts": stages,
        "coverage": coverage(manifest, payloads),
        "missing_count": len(missing),
        "missing_lbas": missing,
        "checkpoint_audit": {"loose": loose_audit, "zip": zip_audit},
        "sector_provenance": provenance,
        "edc_ecc_gate": "PRESERVED_BY_COMPLETE_RAW_SECTOR_SHA256_MATCH",
    }

    if not missing:
        patch_zip = output / f"EXACT_{manifest['sector_count']}_SECTOR_MOSAIC_PATCH.zip"
        result["patch_zip_sha256"] = package(manifest, payloads, patch_zip)
        result["patch_zip"] = str(patch_zip)
        source = find_image(root, manifest["source_size"], manifest["source_sha256"], temp)
        if source:
            target = output / "Sakura_Taisen_2_Disc1_B118_MOSAIC_KO.bin"
            result["output_sha256"] = apply(source, target, manifest, payloads)
            cue = write_cue(target)
            result.update({
                "status": "PASS_EXACT_BIN_CUE_CREATED",
                "output_bin": str(target),
                "output_cue": str(cue),
                "output_cue_sha256": hash_file(cue),
            })
        else:
            result["status"] = "PASS_EXACT_PATCH_PACKAGE_RECOVERED_SOURCE_BIN_PENDING"

    (output / "MOSAIC_RECOVERY_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    shutil.rmtree(temp, ignore_errors=True)
    return result


def selftest() -> dict[str, Any]:
    raw, sector_count = 64, 12
    source = bytearray((i * 17 + 11) & 0xFF for i in range(raw * sector_count))
    target = bytearray(source)
    lbas = (1, 3, 5, 7, 9, 10)
    entries: dict[str, dict[str, str]] = {}
    for lba in lbas:
        before = bytes(source[lba * raw:(lba + 1) * raw])
        after = bytearray(before)
        after[4:23] = bytes(value ^ (lba + 37) for value in after[4:23])
        target[lba * raw:(lba + 1) * raw] = after
        entries[str(lba)] = {
            "original_sha256": hash_bytes(before),
            "patched_sha256": hash_bytes(after),
            "asset": "A" if lba < 7 else "B",
        }

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "original.bin").write_bytes(source)
        checkpoint_a = bytearray(source)
        checkpoint_b = bytearray(source)
        for lba in lbas[:3]:
            checkpoint_a[lba * raw:(lba + 1) * raw] = target[lba * raw:(lba + 1) * raw]
        for lba in lbas[3:5]:
            checkpoint_b[lba * raw:(lba + 1) * raw] = target[lba * raw:(lba + 1) * raw]
        (root / "checkpoint_a.bin").write_bytes(checkpoint_a)
        with zipfile.ZipFile(root / "checkpoint_b.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("nested/checkpoint_b.bin", checkpoint_b)
            last = bytes(target[lbas[-1] * raw:(lbas[-1] + 1) * raw])
            archive.writestr("nested/last_sector.bin", last)
        script = root / "apply.py"
        script.write_text(
            f"SOURCE_SIZE={len(source)}\nSOURCE_SHA='{hash_bytes(source)}'\n"
            f"OUTPUT_SHA='{hash_bytes(target)}'\nRS={raw}\nSECTORS={entries!r}\n",
            encoding="utf-8",
        )
        result = recover_mosaic(script, root, root / "result")
        built = root / "result" / "Sakura_Taisen_2_Disc1_B118_MOSAIC_KO.bin"
        passed = (
            result["status"] == "PASS_EXACT_BIN_CUE_CREATED"
            and built.exists()
            and built.read_bytes() == target
            and result["coverage"]["assets_complete"] == 2
            and result["missing_count"] == 0
        )
    return {"status": "PASS" if passed else "FAIL", "mosaic_roundtrip": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("recover")
    run.add_argument("manifest_script", type=Path)
    run.add_argument("search_root", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("output/B145_MOSAIC"))
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else recover_mosaic(
        args.manifest_script.resolve(), args.search_root.resolve(), args.output_dir.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
