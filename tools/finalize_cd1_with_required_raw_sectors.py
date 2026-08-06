#!/usr/bin/env python3
"""Finalize a 91-asset CD1 candidate with exact required raw sectors.

The input candidate must already be produced by apply_cd1_exact_write_plan.py.
Required sectors are accepted only by exact raw-sector SHA-256. The tool rejects
LBA overlap with any of the 91 planned assets, enforces Expected Write against
the pristine sector hash, validates MODE1/2352 EDC/ECC before and after writing,
and re-extracts all 91 assets after final sector composition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

from mode1_2352 import RAW_SECTOR_SIZE, SYNC, _ecc_compute, edc, verify_mode1_sector

USER_OFFSET = 16
USER_SIZE = 2048
DISC_SIZE = 659_293_824
CHUNK = 4 * 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top level must be object: {path}")
    return value


def extract_asset(fp, lba: int, size: int) -> bytes:
    out = bytearray()
    remaining = size
    index = 0
    while remaining:
        fp.seek((lba + index) * RAW_SECTOR_SIZE)
        sector = fp.read(RAW_SECTOR_SIZE)
        if len(sector) != RAW_SECTOR_SIZE:
            raise ValueError(f"short read at LBA {lba + index}")
        if not verify_mode1_sector(sector)["valid"]:
            raise ValueError(f"MODE1/2352 invalid at LBA {lba + index}")
        take = min(USER_SIZE, remaining)
        out.extend(sector[USER_OFFSET:USER_OFFSET + take])
        remaining -= take
        index += 1
    return bytes(out)


def resolve_sector(root: Path, digest: str, lba: int) -> Path:
    candidates = [root / digest, root / f"{digest}.bin", root / f"LBA{lba}.bin", root / f"lba{lba}.bin"]
    for path in candidates:
        if path.is_file() and path.stat().st_size == RAW_SECTOR_SIZE and sha256_file(path) == digest:
            return path
    raise FileNotFoundError(f"required raw sector missing: LBA {lba} SHA-256 {digest}")


def planned_lbas(operations: list[dict[str, Any]]) -> set[int]:
    occupied: set[int] = set()
    for op in operations:
        lba, size = op.get("lba"), op.get("size")
        if not isinstance(lba, int) or not isinstance(size, int) or size <= 0:
            raise ValueError(f"invalid operation: {op.get('asset')}")
        for raw_lba in range(lba, lba + math.ceil(size / USER_SIZE)):
            if raw_lba in occupied:
                raise ValueError(f"write-plan LBA collision at {raw_lba}")
            occupied.add(raw_lba)
    return occupied


def make_test_sector(seed: int) -> bytes:
    sector = bytearray(RAW_SECTOR_SIZE)
    sector[:12] = SYNC
    sector[12:15] = b"\x00\x02\x00"
    sector[15] = 1
    sector[16:0x810] = bytes((i * 29 + seed) & 0xFF for i in range(2048))
    sector[0x810:0x814] = edc(sector[:0x810]).to_bytes(4, "little")
    sector[0x814:0x81C] = bytes(8)
    sector[0x81C:0x8C8] = _ecc_compute(sector[0x0C:0x81C], 86, 24, 2, 86)
    sector[0x8C8:0x930] = _ecc_compute(sector[0x0C:0x8C8], 52, 43, 86, 88)
    return bytes(sector)


def selftest() -> int:
    a, b = make_test_sector(7), make_test_sector(11)
    assert verify_mode1_sector(a)["valid"] and verify_mode1_sector(b)["valid"]
    assert sha256_bytes(a) != sha256_bytes(b)
    assert planned_lbas([{"asset": "A", "lba": 10, "size": 2049}]) == {10, 11}
    try:
        planned_lbas([{"asset": "A", "lba": 10, "size": 2049}, {"asset": "B", "lba": 11, "size": 1}])
    except ValueError:
        pass
    else:
        raise AssertionError("collision self-test failed")
    print("PASS_FINAL_REQUIRED_SECTOR_SELFTEST")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--plan", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    ap.add_argument("--candidate-disc", type=Path)
    ap.add_argument("--required-manifest", type=Path, action="append", default=[])
    ap.add_argument("--sector-root", type=Path)
    ap.add_argument("--output-disc", type=Path)
    ap.add_argument("--report", type=Path, default=Path("output/BATCH209_FINALIZE_RESULT.json"))
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not all((args.candidate_disc, args.required_manifest, args.sector_root, args.output_disc)):
        ap.error("candidate, required manifest, sector root, and output are required")

    plan = load_json(args.plan)
    operations = plan.get("operations")
    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1" or not isinstance(operations, list) or len(operations) != 91:
        raise ValueError("exact 91-asset plan required")
    occupied = planned_lbas(operations)
    if args.candidate_disc.stat().st_size != DISC_SIZE:
        raise ValueError("candidate Disc size mismatch")

    required = []
    for manifest_path in args.required_manifest:
        manifest = load_json(manifest_path)
        if manifest.get("format") != "ST2-CD1-REQUIRED-LEGACY-SECTOR-v1":
            raise ValueError(f"unsupported required-sector manifest: {manifest_path}")
        sector = manifest.get("sector", {})
        lba = sector.get("lba")
        if not isinstance(lba, int) or lba < 0 or lba in occupied:
            raise ValueError(f"required sector overlaps 91-asset plan or has invalid LBA: {lba}")
        required_sha = sector.get("required_sha256")
        pristine_sha = sector.get("pristine_sha256")
        if not all(isinstance(x, str) and len(x) == 64 for x in (required_sha, pristine_sha)):
            raise ValueError(f"invalid sector hashes: {manifest_path}")
        required.append((manifest_path, lba, pristine_sha, required_sha, resolve_sector(args.sector_root, required_sha, lba)))

    args.output_disc.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.candidate_disc, args.output_disc)
    sector_results = []
    try:
        with args.output_disc.open("r+b") as fp:
            for manifest_path, lba, pristine_sha, required_sha, payload_path in required:
                fp.seek(lba * RAW_SECTOR_SIZE)
                before = fp.read(RAW_SECTOR_SIZE)
                if len(before) != RAW_SECTOR_SIZE or sha256_bytes(before) != pristine_sha:
                    raise ValueError(f"Expected Write failed for required LBA {lba}")
                if not verify_mode1_sector(before)["valid"]:
                    raise ValueError(f"pre-write EDC/ECC failed for LBA {lba}")
                payload = payload_path.read_bytes()
                if sha256_bytes(payload) != required_sha or not verify_mode1_sector(payload)["valid"]:
                    raise ValueError(f"required payload hash or EDC/ECC failed for LBA {lba}")
                fp.seek(lba * RAW_SECTOR_SIZE)
                fp.write(payload)
                fp.seek(lba * RAW_SECTOR_SIZE)
                after = fp.read(RAW_SECTOR_SIZE)
                if sha256_bytes(after) != required_sha or not verify_mode1_sector(after)["valid"]:
                    raise ValueError(f"post-write gate failed for LBA {lba}")
                sector_results.append({"manifest": manifest_path.as_posix(), "lba": lba, "required_sha256": required_sha, "expected_write": "PASS", "mode1_2352_edc_ecc": "PASS", "post_write_sha256": "PASS"})

            asset_results = []
            for op in operations:
                payload = extract_asset(fp, op["lba"], op["size"])
                digest = sha256_bytes(payload)
                if digest != op["replacement_sha256"]:
                    raise ValueError(f"post-finalization re-extraction mismatch: {op['asset']}")
                asset_results.append({"asset": op["asset"], "replacement_sha256": digest, "reextraction": "PASS"})
    except Exception:
        args.output_disc.unlink(missing_ok=True)
        raise

    report = {
        "batch": 209,
        "status": "PASS_91_ASSETS_PLUS_REQUIRED_RAW_SECTORS_FINALIZED",
        "input_candidate_sha256": sha256_file(args.candidate_disc),
        "output_disc_sha256": sha256_file(args.output_disc),
        "required_sector_count": len(sector_results),
        "required_sectors": sector_results,
        "asset_count": len(asset_results),
        "reextraction": "91/91 PASS",
        "gates": {"expected_write": "PASS", "mode1_2352_edc_ecc": "PASS", "estimated_bytes": 0},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
