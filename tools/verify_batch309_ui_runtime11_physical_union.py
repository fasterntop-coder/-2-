#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE = 659_293_824
USER_DATA_OFFSET = 16
USER_DATA_SIZE = 2048
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
B308_SHA256 = "b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f"
B309_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED = 90_272
EXPECTED_ASSETS = 11
EXPECTED_FOOTPRINT_SECTORS = 1_174
EXPECTED_NEW_CHANGED = 144
SUCCESS = "PASS_B309_DISC_ASSET_REEXTRACTION_AND_ALL_CHANGED_SECTOR_GATE"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def extract_mode1_asset(raw_bin: Path, lba: int, size: int) -> bytes:
    remaining = size
    out = bytearray()
    with raw_bin.open("rb") as f:
        sector = lba
        while remaining:
            f.seek(sector * RAW_SECTOR_SIZE + USER_DATA_OFFSET)
            take = min(USER_DATA_SIZE, remaining)
            chunk = f.read(take)
            if len(chunk) != take:
                die(f"short read extracting LBA {lba} size {size} at sector {sector}")
            out.extend(chunk)
            remaining -= take
            sector += 1
    return bytes(out)


def validate_manifest(manifest: dict) -> list[dict]:
    if manifest.get("batch") != 309:
        die("manifest batch")
    if manifest.get("status") != "PASS_B309_B308_PLUS_R39_UI_RUNTIME11_PHYSICAL_UNION":
        die("manifest status")
    if manifest.get("pristine_sha256") != PRISTINE_SHA256:
        die("manifest pristine SHA-256")

    parent = manifest.get("parent", {})
    if parent.get("batch") != 308 or parent.get("sha256") != B308_SHA256:
        die("manifest parent Batch308 lineage")
    if parent.get("core_inventory") != "223/223 PASS":
        die("manifest Batch308 core inventory")

    scope = manifest.get("scope", {})
    if scope.get("supplemental_assets") != EXPECTED_ASSETS:
        die("manifest supplemental asset count")

    physical = manifest.get("physical_result", {})
    expected_exact = {
        "new_footprint_sectors": EXPECTED_FOOTPRINT_SECTORS,
        "new_changed_sectors": EXPECTED_NEW_CHANGED,
        "expected_write_records": EXPECTED_FOOTPRINT_SECTORS,
        "new_asset_reextraction": "11/11 PASS",
        "cumulative_changed_sectors": EXPECTED_CHANGED,
        "all_changed_sector_mode1_edc_ecc": "90272/90272 PASS",
        "lba_collisions": 0,
        "outside_footprint_changes": 0,
        "third_variant_assets": 0,
        "guessed_payload_bytes": 0,
        "output_sha256": B309_SHA256,
    }
    for key, expected in expected_exact.items():
        if physical.get(key) != expected:
            die(f"manifest physical_result.{key}")

    assets = manifest.get("assets", [])
    if len(assets) != EXPECTED_ASSETS:
        die(f"manifest asset list count {len(assets)} != {EXPECTED_ASSETS}")

    seen_paths: set[str] = set()
    for asset in assets:
        for required in ("path", "lba", "size", "source_sha256", "candidate_sha256"):
            if required not in asset:
                die(f"manifest asset missing {required}")
        path = str(asset["path"])
        if path in seen_paths:
            die(f"duplicate manifest asset {path}")
        seen_paths.add(path)
        if int(asset["lba"]) < 0 or int(asset["size"]) <= 0:
            die(f"invalid LBA/size for {path}")
    return assets


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Re-verify the exact Batch309 Disc1 candidate: parent lineage, 11 supplemental "
            "whole assets from pristine/candidate, exact changed-sector accounting, and MODE1 EDC/ECC."
        )
    )
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output-report", type=Path, required=True)
    args = ap.parse_args()

    for p in (args.pristine_bin, args.candidate_bin, args.manifest):
        if not p.is_file():
            die(f"missing input {p}")
    for p in (args.pristine_bin, args.candidate_bin):
        if p.stat().st_size != DISC_SIZE:
            die(f"unexpected Disc size for {p}: {p.stat().st_size}")

    pristine_sha = sha256_file(args.pristine_bin)
    if pristine_sha != PRISTINE_SHA256:
        die("pristine SHA-256")
    candidate_sha = sha256_file(args.candidate_bin)
    if candidate_sha != B309_SHA256:
        die("Batch309 candidate SHA-256")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    assets = validate_manifest(manifest)

    asset_results = []
    for asset in assets:
        path = str(asset["path"])
        lba = int(asset["lba"])
        size = int(asset["size"])
        source_bytes = extract_mode1_asset(args.pristine_bin, lba, size)
        candidate_bytes = extract_mode1_asset(args.candidate_bin, lba, size)
        source_sha = sha256_bytes(source_bytes)
        output_sha = sha256_bytes(candidate_bytes)
        if source_sha != asset["source_sha256"]:
            die(f"pristine whole-asset SHA-256 mismatch: {path}")
        if output_sha != asset["candidate_sha256"]:
            die(f"candidate whole-asset SHA-256 mismatch: {path}")
        asset_results.append(
            {
                "path": path,
                "lba": lba,
                "size": size,
                "source_sha256": source_sha,
                "candidate_sha256": output_sha,
                "status": "PASS",
            }
        )

    changed_count = 0
    invalid_lbas: list[int] = []
    with args.pristine_bin.open("rb") as src, args.candidate_bin.open("rb") as out:
        lba = 0
        while True:
            a = src.read(RAW_SECTOR_SIZE)
            b = out.read(RAW_SECTOR_SIZE)
            if not a and not b:
                break
            if len(a) != RAW_SECTOR_SIZE or len(b) != RAW_SECTOR_SIZE:
                die(f"short raw sector at LBA {lba}")
            if a != b:
                changed_count += 1
                check = verify_mode1_sector(b)
                if not check.get("valid"):
                    invalid_lbas.append(lba)
            lba += 1

    if changed_count != EXPECTED_CHANGED:
        die(f"changed sector count {changed_count} != {EXPECTED_CHANGED}")
    if invalid_lbas:
        die(f"invalid MODE1 EDC/ECC sectors: {invalid_lbas[:16]}")

    report = {
        "batch": 309,
        "status": SUCCESS,
        "pristine_sha256": pristine_sha,
        "candidate_sha256": candidate_sha,
        "candidate_size": DISC_SIZE,
        "parent_batch": 308,
        "parent_sha256": B308_SHA256,
        "core_inventory_certificate": "223/223 PASS",
        "supplemental_assets_reextracted": f"{len(asset_results)}/{EXPECTED_ASSETS} PASS",
        "supplemental_assets": asset_results,
        "expected_write_records_certificate": EXPECTED_FOOTPRINT_SECTORS,
        "supplemental_footprint_sectors_certificate": EXPECTED_FOOTPRINT_SECTORS,
        "supplemental_new_changed_sectors_certificate": EXPECTED_NEW_CHANGED,
        "changed_sector_count": changed_count,
        "changed_sector_edc_ecc": f"{changed_count}/{changed_count} PASS",
        "changed_sector_accounting": "EXACT_PRISTINE_VS_OUTPUT_DIFF",
        "outside_footprint_changes_certificate": 0,
        "third_variant_assets_certificate": 0,
        "guessed_payload_bytes": 0,
        "hardware_validation": "PENDING; this verifier certifies exact physical bytes/gates, not playback behavior",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(SUCCESS)
    print("candidate_sha256=" + candidate_sha)
    print(f"supplemental_assets={len(asset_results)}/{EXPECTED_ASSETS} PASS")
    print(f"changed_sector_edc_ecc={changed_count}/{changed_count} PASS")


if __name__ == "__main__":
    main()
