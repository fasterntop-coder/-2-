#!/usr/bin/env python3
"""Verify the permanent CD1 legacy-sector preservation gate.

The manifest is always validated. When --disc is supplied, the exact raw sector
is read from the candidate MODE1/2352 BIN and checked by SHA-256. No bytes are
written and no payload is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

RAW_SECTOR_SIZE = 2352
EXPECTED_SOURCE_SIZE = 659_293_824
EXPECTED_SOURCE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
EXPECTED_LBA = 208_689
EXPECTED_PRISTINE_SHA = "3da035f48eb2cdd51b4248b5881b1fe2f30f0779234ce553eca7387286df0246"
EXPECTED_REQUIRED_SHA = "97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("manifests/CD1_REQUIRED_LEGACY_SECTOR_LBA208689.json"))
    ap.add_argument("--disc", type=Path)
    args = ap.parse_args()

    m = json.loads(args.manifest.read_text(encoding="utf-8"))
    if m.get("format") != "ST2-CD1-REQUIRED-LEGACY-SECTOR-v1":
        raise ValueError("unsupported manifest format")
    source = m.get("source_disc", {})
    sector = m.get("sector", {})
    gates = m.get("gates", {})
    checks = {
        "source_size": source.get("size") == EXPECTED_SOURCE_SIZE,
        "source_sha": source.get("sha256") == EXPECTED_SOURCE_SHA,
        "raw_format": source.get("format") == "MODE1/2352",
        "lba": sector.get("lba") == EXPECTED_LBA,
        "raw_size": sector.get("raw_size") == RAW_SECTOR_SIZE,
        "pristine_sha": sector.get("pristine_sha256") == EXPECTED_PRISTINE_SHA,
        "required_sha": sector.get("required_sha256") == EXPECTED_REQUIRED_SHA,
        "expected_write": gates.get("expected_write") == "REQUIRED",
        "edc_ecc": gates.get("mode1_2352_edc_ecc") == "REQUIRED",
        "post_build_hash": gates.get("post_build_sector_sha256") == "REQUIRED",
        "no_estimated_bytes": gates.get("estimated_bytes") == 0,
    }
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise ValueError("manifest gate failed: " + ", ".join(failed))

    if args.disc is None:
        print("PASS_REQUIRED_LEGACY_SECTOR_MANIFEST")
        return 0
    if args.disc.stat().st_size != EXPECTED_SOURCE_SIZE:
        raise ValueError("candidate Disc size mismatch")
    with args.disc.open("rb") as f:
        f.seek(EXPECTED_LBA * RAW_SECTOR_SIZE)
        raw = f.read(RAW_SECTOR_SIZE)
    if len(raw) != RAW_SECTOR_SIZE:
        raise ValueError("candidate sector truncated")
    actual = digest(raw)
    if actual != EXPECTED_REQUIRED_SHA:
        raise ValueError(f"LBA {EXPECTED_LBA} regression: {actual}")
    print("PASS_REQUIRED_LEGACY_SECTOR_PRESENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
