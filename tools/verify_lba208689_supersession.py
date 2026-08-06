#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

RAW = 2352
LBA = 208689
ASSET_LBA = 208663
ASSET_SIZE = 82048
EXPECTED_DISC_SIZE = 659293824
EXPECTED_SECTOR_SHA = "3da035f48eb2cdd51b4248b5881b1fe2f30f0779234ce553eca7387286df0246"
EXPECTED_ASSET_SHA = "70a624feeca087f10cfc82f929d4d80aeb21f45642c2d1996ab6a967aa48297d"
FORBIDDEN_LEGACY_SHA = "97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0"

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def extract_user_data(path: Path, lba: int, size: int) -> bytes:
    out = bytearray()
    remaining = size
    with path.open("rb") as f:
        while remaining:
            f.seek(lba * RAW + 16)
            take = min(2048, remaining)
            block = f.read(take)
            if len(block) != take:
                raise ValueError("unexpected EOF during asset extraction")
            out += block
            remaining -= take
            lba += 1
    return bytes(out)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", type=Path)
    ap.add_argument("--output", type=Path, default=Path("output/BATCH222_LBA208689_SUPERSESSION_RESULT.json"))
    args = ap.parse_args()
    if not args.candidate.is_file() or args.candidate.stat().st_size != EXPECTED_DISC_SIZE:
        raise SystemExit("candidate Disc size mismatch")
    with args.candidate.open("rb") as f:
        f.seek(LBA * RAW)
        sector = f.read(RAW)
    sector_sha = sha256(sector)
    if sector_sha == FORBIDDEN_LEGACY_SHA:
        raise SystemExit("forbidden legacy LBA208689 override detected; exact STNSYS03 would be corrupted")
    if sector_sha != EXPECTED_SECTOR_SHA:
        raise SystemExit(f"unexpected LBA208689 sector SHA: {sector_sha}")
    asset_sha = sha256(extract_user_data(args.candidate, ASSET_LBA, ASSET_SIZE))
    if asset_sha != EXPECTED_ASSET_SHA:
        raise SystemExit(f"STNSYS03 exact asset SHA mismatch: {asset_sha}")
    result = {
        "batch": 222,
        "status": "PASS_LBA208689_SUPERSEDED_BY_EXACT_STNSYS03",
        "candidate": str(args.candidate),
        "lba208689_sha256": sector_sha,
        "stnsys03_sha256": asset_sha,
        "forbidden_legacy_sector_sha256": FORBIDDEN_LEGACY_SHA,
        "estimated_bytes": 0,
        "disc_bytes_written": 0
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["status"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
