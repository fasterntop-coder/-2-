#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE = 659_293_824
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
B308_SHA256 = "b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f"
EXPECTED_CHANGED = 90_128
EXPECTED_ASSETS = 223
SUCCESS = "PASS_B308_FINAL_DISC_SHA_AND_ALL_CHANGED_SECTOR_GATE"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Re-verify the exact Batch308 Disc1 physical/static 223/223 candidate against pristine."
    )
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--output-report", type=Path, required=True)
    args = ap.parse_args()

    for p in (args.pristine_bin, args.candidate_bin):
        if p.stat().st_size != DISC_SIZE:
            die(f"unexpected Disc size for {p}: {p.stat().st_size}")

    if sha256_file(args.pristine_bin) != PRISTINE_SHA256:
        die("pristine SHA-256")
    candidate_sha = sha256_file(args.candidate_bin)
    if candidate_sha != B308_SHA256:
        die("Batch308 candidate SHA-256")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("batch") != 308:
        die("manifest batch")
    if manifest.get("status") != "PASS_B308_FINAL_223_OF_223_WHOLE_ASSET_AND_ALL_CHANGED_SECTOR_GATE":
        die("manifest status")
    final = manifest.get("final_accounting", {})
    if final.get("logical_and_physical_static_assets") != "223/223":
        die("223/223 accounting")
    if manifest.get("final_gates", {}).get("whole_asset_reextraction") != "223/223 PASS":
        die("whole-asset gate certificate")
    if manifest.get("final_gates", {}).get("guessed_payload_bytes") != 0:
        die("guessed bytes")

    changed = []
    invalid = []
    with args.pristine_bin.open("rb") as src, args.candidate_bin.open("rb") as out:
        lba = 0
        while True:
            a = src.read(RAW_SECTOR_SIZE)
            b = out.read(RAW_SECTOR_SIZE)
            if not a and not b:
                break
            if len(a) != len(b):
                die("Disc length mismatch during sector accounting")
            if a != b:
                changed.append(lba)
                check = verify_mode1_sector(b)
                if not check.get("valid"):
                    invalid.append(lba)
            lba += 1

    if len(changed) != EXPECTED_CHANGED:
        die(f"changed sector count {len(changed)} != {EXPECTED_CHANGED}")
    if invalid:
        die(f"invalid MODE1 EDC/ECC sectors: {invalid[:16]}")

    report = {
        "batch": 308,
        "status": SUCCESS,
        "candidate_sha256": candidate_sha,
        "candidate_size": DISC_SIZE,
        "logical_assets": EXPECTED_ASSETS,
        "manifest_whole_asset_reextraction": "223/223 PASS",
        "changed_sector_count": len(changed),
        "changed_sector_edc_ecc": f"{len(changed)}/{len(changed)} PASS",
        "changed_sector_accounting": "EXACT_PRISTINE_VS_OUTPUT_DIFF",
        "guessed_payload_bytes": 0,
        "hardware_validation": "PENDING; this verifier certifies the exact physical/static candidate, not playback validation",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(SUCCESS)
    print("candidate_sha256=" + candidate_sha)
    print(f"changed_sector_edc_ecc={len(changed)}/{len(changed)} PASS")


if __name__ == "__main__":
    main()
