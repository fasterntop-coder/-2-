#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys, zipfile
from pathlib import Path

EXPECTED_ZIP_SHA256 = "48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c"
EXPECTED_ZIP_SIZE = 3298916
EXPECTED_SECTORS = 1597
EXPECTED_ASSETS = 55
EXPECTED_OUTPUT_SHA256 = "b5e8fc8b1a5798d03a3f3bd21a87ce66b742c64a1d8ce3ed3d7dc8db9763d518"
REQUIRED = {
    "BATCH137_PACKAGE_MANIFEST.json",
    "BATCH137_DELTA_MANIFEST.json",
    "BATCH137_REEXTRACTION_AUDIT.csv",
    "BATCH137_SECTOR_AUDIT.csv",
    "BATCH137_VALIDATION_RESULT.json",
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fail(msg: str) -> None:
    raise SystemExit(f"FAIL: {msg}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", type=Path)
    args = ap.parse_args()
    raw = args.package.read_bytes()
    if len(raw) != EXPECTED_ZIP_SIZE: fail("package size mismatch")
    if sha256(raw) != EXPECTED_ZIP_SHA256: fail("package SHA-256 mismatch")
    with zipfile.ZipFile(args.package) as z:
        names = set(z.namelist())
        missing = REQUIRED - names
        if missing: fail(f"missing members: {sorted(missing)}")
        package_manifest = json.loads(z.read("BATCH137_PACKAGE_MANIFEST.json"))
        for name, meta in package_manifest.items():
            if name not in names: fail(f"manifest member absent: {name}")
            data = z.read(name)
            if len(data) != meta["size"]: fail(f"size mismatch: {name}")
            if sha256(data) != meta["sha256"]: fail(f"SHA mismatch: {name}")
        delta = json.loads(z.read("BATCH137_DELTA_MANIFEST.json"))
        if len(delta) != EXPECTED_SECTORS: fail("delta sector count mismatch")
        assets = set()
        for lba, meta in delta.items():
            if int(lba) < 0: fail("negative LBA")
            assets.add(meta["asset"])
            member = meta["file"]
            if member not in names: fail(f"missing delta: {member}")
            if sha256(z.read(member)) != meta["delta_sha256"]: fail(f"delta SHA mismatch: {member}")
            for key in ("original_sha256", "patched_sha256"):
                if len(meta[key]) != 64: fail(f"bad {key}: {lba}")
        if len(assets) != EXPECTED_ASSETS: fail("asset count mismatch")
        result = json.loads(z.read("BATCH137_VALIDATION_RESULT.json"))
        if result["status"] != "PASS_FIFTYFIVE_ASSET_EXACT_RECOVERY": fail("validation status mismatch")
        if result["changed_raw_sectors"] != EXPECTED_SECTORS: fail("validation sector mismatch")
        if result["exact_assets"] != EXPECTED_ASSETS: fail("validation asset mismatch")
        if result["edc_ecc"] != "PASS" or result["reextraction"] != "55/55 PASS": fail("safety gate mismatch")
        if result["output_bin_sha256"] != EXPECTED_OUTPUT_SHA256: fail("output BIN SHA mismatch")
    print(json.dumps({"status":"PASS_BATCH169_B137_PACKAGE_LOCKED","package_sha256":EXPECTED_ZIP_SHA256,"assets":55,"sectors":1597,"edc_ecc":"PASS","reextraction":"55/55 PASS"}, indent=2))

if __name__ == "__main__":
    main()
