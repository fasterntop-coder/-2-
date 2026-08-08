#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

RAW = 2352
USER_OFF = 16
USER = 2048
SYNC = bytes([0] + [0xFF] * 10 + [0])
PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PARENT_SHA = "dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83"
EXPECTED_ASSETS = 10


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _edc_lut() -> list[int]:
    out = []
    for i in range(256):
        v = i
        for _ in range(8):
            v = (v >> 1) ^ (0xD8018001 if v & 1 else 0)
        out.append(v & 0xFFFFFFFF)
    return out


EDC_LUT = _edc_lut()


def edc(data: bytes) -> int:
    v = 0
    for b in data:
        v = (v >> 8) ^ EDC_LUT[(v ^ b) & 255]
    return v & 0xFFFFFFFF


def _ecc_luts() -> tuple[list[int], list[int]]:
    f = [0] * 256
    b = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        f[i] = j & 255
        b[i ^ f[i]] = i
    return f, b


ECC_F, ECC_B = _ecc_luts()


def ecc(src: bytes, major_count: int, minor_count: int, major_mult: int, minor_inc: int) -> bytes:
    size = major_count * minor_count
    dest = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        dest[major] = a
        dest[major + major_count] = a ^ b
    return bytes(dest)


def verify_mode1(sector: bytes) -> dict[str, bool]:
    if len(sector) != RAW:
        return {"valid": False}
    r = {
        "size": True,
        "sync": sector[:12] == SYNC,
        "mode": sector[15] == 1,
        "edc": int.from_bytes(sector[0x810:0x814], "little") == edc(sector[:0x810]),
        "reserved": sector[0x814:0x81C] == bytes(8),
        "ecc_p": sector[0x81C:0x8C8] == ecc(sector[0x0C:0x81C], 86, 24, 2, 86),
        "ecc_q": sector[0x8C8:0x930] == ecc(sector[0x0C:0x8C8], 52, 43, 86, 88),
    }
    r["valid"] = all(r.values())
    return r


def rebuild_mode1(raw: bytes, user: bytes) -> bytes:
    if len(raw) != RAW or len(user) != USER:
        raise ValueError("sector geometry mismatch")
    b = bytearray(raw)
    b[USER_OFF:USER_OFF + USER] = user
    b[0x810:0x814] = edc(bytes(b[:0x810])).to_bytes(4, "little")
    b[0x814:0x81C] = bytes(8)
    b[0x81C:0x8C8] = ecc(bytes(b[0x0C:0x81C]), 86, 24, 2, 86)
    b[0x8C8:0x930] = ecc(bytes(b[0x0C:0x8C8]), 52, 43, 86, 88)
    out = bytes(b)
    if not verify_mode1(out).get("valid"):
        raise ValueError("rebuilt MODE1 EDC/ECC failure")
    return out


def extract_user(disc: Path, lba: int, size: int) -> bytes:
    out = bytearray()
    remain = size
    with disc.open("rb") as f:
        while remain:
            f.seek(lba * RAW)
            raw = f.read(RAW)
            if len(raw) != RAW or raw[:12] != SYNC or raw[15] != 1:
                raise ValueError(f"not MODE1/2352 at LBA {lba}")
            take = min(USER, remain)
            out += raw[USER_OFF:USER_OFF + take]
            remain -= take
            lba += 1
    return bytes(out)


def diff_lbas(left: Path, right: Path) -> list[int]:
    out = []
    with left.open("rb") as a, right.open("rb") as b:
        lba = 0
        while True:
            x, y = a.read(RAW), b.read(RAW)
            if not x and not y:
                break
            if len(x) != len(y):
                raise ValueError("disc size mismatch")
            if x != y:
                out.append(lba)
            lba += 1
    return out


def load_manifest(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("format") != "ST2-CD1-BATCH241-VIDEO10-CONSOLIDATED-MANIFEST-v1":
        raise SystemExit("unexpected Batch241 consolidated manifest format")
    if obj.get("physical_parent_disc_sha256") != PARENT_SHA:
        raise SystemExit("manifest parent SHA mismatch")
    assets = obj.get("replacement_files", [])
    if len(assets) != EXPECTED_ASSETS:
        raise SystemExit(f"expected {EXPECTED_ASSETS} assets, got {len(assets)}")
    names = [Path(x["iso_path"]).name for x in assets]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate asset name")
    return assets


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch242: safely integrate recovered Batch241 Video10 into exact Batch240 parent")
    ap.add_argument("--pristine", type=Path, required=True)
    ap.add_argument("--parent", type=Path, required=True)
    ap.add_argument("--candidate-dir", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("Sakura_Taisen_2_Disc1_B242_KO.bin"))
    ap.add_argument("--result", type=Path, default=Path("BATCH242_RESULT.json"))
    args = ap.parse_args()

    if sha_file(args.pristine) != PRISTINE_SHA:
        raise SystemExit("pristine Disc SHA mismatch")
    if sha_file(args.parent) != PARENT_SHA:
        raise SystemExit("Batch240 parent SHA mismatch")

    assets = load_manifest(args.manifest)
    footprint: set[int] = set()
    per_asset: dict[str, dict] = {}

    for asset in assets:
        name = Path(asset["iso_path"]).name
        candidate = args.candidate_dir / name
        if not candidate.is_file():
            raise SystemExit(f"missing exact candidate: {name}")
        if candidate.stat().st_size != asset["size"]:
            raise SystemExit(f"candidate size mismatch: {name}")
        actual = sha_file(candidate)
        if actual != asset["replacement_sha256"]:
            raise SystemExit(f"candidate SHA mismatch: {name}: {actual}")
        pristine_asset = extract_user(args.pristine, asset["lba"], asset["size"])
        if sha_bytes(pristine_asset) != asset["source_sha256"]:
            raise SystemExit(f"source asset SHA mismatch: {name}")
        sector_count = math.ceil(asset["size"] / USER)
        ls = set(range(asset["lba"], asset["lba"] + sector_count))
        if footprint & ls:
            raise SystemExit(f"Video10 self-overlap: {name}")
        footprint |= ls
        per_asset[name] = {
            "lba_first": asset["lba"],
            "lba_last": asset["lba"] + sector_count - 1,
            "footprint_sectors": sector_count,
            "candidate_sha256": actual,
        }

    with args.pristine.open("rb") as src, args.parent.open("rb") as parent:
        for lba in sorted(footprint):
            src.seek(lba * RAW)
            parent.seek(lba * RAW)
            if src.read(RAW) != parent.read(RAW):
                raise SystemExit(f"Batch240 parent overlaps Video10 footprint at LBA {lba}")

    old_changed = diff_lbas(args.pristine, args.parent)
    if set(old_changed) & footprint:
        raise SystemExit("Batch240 changed-sector overlap with Video10 footprint")

    shutil.copyfile(args.parent, args.output)
    expected_write: list[dict] = []
    new_changed: list[int] = []

    try:
        with args.pristine.open("rb") as pristine_f, args.parent.open("rb") as parent_f, args.output.open("r+b") as dst:
            for asset in assets:
                name = Path(asset["iso_path"]).name
                payload = (args.candidate_dir / name).read_bytes()
                remain, pos, lba, changed_count = asset["size"], 0, asset["lba"], 0
                while remain:
                    pristine_f.seek(lba * RAW)
                    parent_f.seek(lba * RAW)
                    source_raw = pristine_f.read(RAW)
                    parent_raw = parent_f.read(RAW)
                    if source_raw != parent_raw:
                        raise ValueError(f"Expected Write parent mismatch at LBA {lba}")
                    take = min(USER, remain)
                    old_user = parent_raw[USER_OFF:USER_OFF + USER]
                    new_user = bytearray(old_user)
                    new_user[:take] = payload[pos:pos + take]
                    changed = bytes(new_user) != old_user
                    patched = parent_raw
                    if changed:
                        patched = rebuild_mode1(parent_raw, bytes(new_user))
                        dst.seek(lba * RAW)
                        dst.write(patched)
                        new_changed.append(lba)
                        changed_count += 1
                    expected_write.append({
                        "asset": name,
                        "lba": lba,
                        "source_sector_sha256": sha_bytes(source_raw),
                        "parent_sector_sha256": sha_bytes(parent_raw),
                        "patched_sector_sha256": sha_bytes(patched),
                        "changed": changed,
                    })
                    remain -= take
                    pos += take
                    lba += 1
                per_asset[name]["changed_sectors"] = changed_count

        parent_delta = diff_lbas(args.parent, args.output)
        if set(parent_delta) != set(new_changed):
            raise ValueError("parent delta / Expected Write accounting mismatch")
        if not set(new_changed) <= footprint:
            raise ValueError("change outside approved Video10 footprint")

        with args.output.open("rb") as f:
            for lba in new_changed:
                f.seek(lba * RAW)
                check = verify_mode1(f.read(RAW))
                if not check.get("valid"):
                    raise ValueError(f"changed output EDC/ECC failure at LBA {lba}: {check}")

        for asset in assets:
            name = Path(asset["iso_path"]).name
            actual = sha_bytes(extract_user(args.output, asset["lba"], asset["size"]))
            if actual != asset["replacement_sha256"]:
                raise ValueError(f"whole-asset re-extraction failed: {name}: {actual}")

        union = diff_lbas(args.pristine, args.output)
        expected_union = set(old_changed) | set(new_changed)
        if set(union) != expected_union:
            raise ValueError("full-disc changed-sector union accounting mismatch")

        final_sha = sha_file(args.output)
        result = {
            "batch": 242,
            "status": "PASS_BATCH240_PLUS_VIDEO10_PHYSICAL_UNION",
            "pristine_disc_sha256": PRISTINE_SHA,
            "parent_disc_sha256": PARENT_SHA,
            "output_disc_sha256": final_sha,
            "new_assets": EXPECTED_ASSETS,
            "new_footprint_sectors": len(footprint),
            "new_changed_sectors": len(new_changed),
            "previous_changed_sectors": len(old_changed),
            "union_changed_sectors": len(union),
            "parent_overlap": 0,
            "outside_footprint_changes": 0,
            "changed_sector_mode1_edc_ecc": f"{len(new_changed)}/{len(new_changed)} PASS",
            "whole_asset_reextraction": f"{EXPECTED_ASSETS}/{EXPECTED_ASSETS} PASS",
            "expected_write_records": len(expected_write),
            "per_asset": per_asset,
            "safety": {
                "guessed_payload_bytes": False,
                "candidate_sha256_required": True,
                "source_asset_sha256_required": True,
                "source_raw_expected_write": True,
                "parent_overlap_gate": True,
                "changed_sector_edc_ecc": True,
                "whole_asset_reextraction": True,
                "full_disc_distributed": False,
            },
        }
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        args.output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
