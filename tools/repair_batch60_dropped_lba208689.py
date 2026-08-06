#!/usr/bin/env python3
"""Repair the one exact sector dropped between legacy Batch55 and Batch59/60.

Inputs:
- exact Batch60 replay BIN
- exact Batch55 package directory containing patch_manifest.json and payload

The tool verifies every relevant SHA-256 before writing LBA 208689, validates the
raw sector's MODE1/2352 EDC/ECC, verifies the repaired whole-BIN SHA, and deletes
the output on any failure. No bytes are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from mode1_2352 import assert_mode1_sector

RAW_SECTOR_SIZE = 2352
TARGET_LBA = 208689
BATCH60_SHA256 = "7f57743b947704963290e2e108485262c940690c4a3c8d60800a7ae3338f397d"
BATCH55_SECTOR_SHA256 = "97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0"
REPAIRED_SHA256 = "845a6ec09fcf846bbae9a996d63966692908c9fc85d6a2e5a518c9b06f4cbe21"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def recover_sector(package: Path) -> bytes:
    manifest_path = package / "patch_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("payload_ranges", []):
        start = int(item["start_sector"])
        count = int(item["sector_count"])
        if not start <= TARGET_LBA < start + count:
            continue
        payload_path = package / item["file"]
        payload = payload_path.read_bytes()
        if len(payload) != count * RAW_SECTOR_SIZE:
            raise ValueError("Batch55 payload size mismatch")
        if hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise ValueError("Batch55 payload SHA mismatch")
        offset = (TARGET_LBA - start) * RAW_SECTOR_SIZE
        sector = payload[offset:offset + RAW_SECTOR_SIZE]
        if hashlib.sha256(sector).hexdigest() != BATCH55_SECTOR_SHA256:
            raise ValueError("Batch55 LBA 208689 sector SHA mismatch")
        assert_mode1_sector(sector, "Batch55 LBA 208689")
        return sector
    raise ValueError("Batch55 package does not contain LBA 208689")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch60_bin", type=Path)
    parser.add_argument("batch55_package", type=Path)
    parser.add_argument("output_bin", type=Path)
    args = parser.parse_args()

    if sha256_file(args.batch60_bin) != BATCH60_SHA256:
        raise ValueError("Batch60 input BIN SHA mismatch")
    sector = recover_sector(args.batch55_package)

    try:
        shutil.copyfile(args.batch60_bin, args.output_bin)
        with args.output_bin.open("r+b") as stream:
            stream.seek(TARGET_LBA * RAW_SECTOR_SIZE)
            stream.write(sector)
        actual = sha256_file(args.output_bin)
        if actual != REPAIRED_SHA256:
            raise ValueError(f"repaired BIN SHA mismatch: {actual}")
    except Exception:
        args.output_bin.unlink(missing_ok=True)
        raise

    print("PASS_BATCH60_LBA208689_EXACT_REPAIR")
    print(REPAIRED_SHA256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
