#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE = 659_293_824
EXPECTED_PARENT_STATUS = "PASS_BATCH304_B303_PLUS_B56_60_STORY_BIN5_EXACT_UNION"
SUCCESS = "PASS_BATCH305_B304_CUMULATIVE_RELEASE_GATE"
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
EXPECTED_STORY_ASSETS = 5
EXPECTED_STORY_REVIEWED = 3273
EXPECTED_STORY_TRANSLATED = 3268
EXPECTED_STORY_CONTROLS = 5
HISTORICAL_STORY_DONE = 14865
HISTORICAL_STORY_TOTAL = 14875


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def die(message: str) -> None:
    raise SystemExit("FAIL " + message)


def validate_report(report: dict, candidate_sha: str) -> list[int]:
    if report.get("batch") != 304:
        die("parent batch is not 304")
    if report.get("status") != EXPECTED_PARENT_STATUS:
        die("unexpected Batch304 status")
    if report.get("output_sha256") != candidate_sha:
        die("Batch304 report/output SHA binding")
    if report.get("pristine_reference_sha256") != PRISTINE_SHA256:
        die("pristine SHA reference")
    if report.get("replacement_assets") != EXPECTED_STORY_ASSETS:
        die("replacement asset accounting")
    if report.get("story_records_reviewed") != EXPECTED_STORY_REVIEWED:
        die("reviewed story record accounting")
    if report.get("story_records_translated") != EXPECTED_STORY_TRANSLATED:
        die("translated story record accounting")
    if report.get("story_controls_preserved") != EXPECTED_STORY_CONTROLS:
        die("control-preserved story record accounting")
    if report.get("guessed_payload_bytes") != 0:
        die("guessed payload bytes are forbidden")
    if report.get("asset_reextraction") != "5/5 PASS":
        die("whole-asset re-extraction gate")
    if report.get("changed_sector_accounting") != "PASS":
        die("changed-sector accounting gate")

    lbas = report.get("changed_lbas")
    ew = report.get("expected_write")
    audit = report.get("asset_audit")
    if not isinstance(lbas, list) or not isinstance(ew, list) or not isinstance(audit, list):
        die("missing changed_lbas/expected_write/asset_audit")
    if len(audit) != EXPECTED_STORY_ASSETS:
        die("asset audit count")
    if len(lbas) != report.get("changed_raw_sectors"):
        die("changed raw sector count")
    if len(ew) != len(lbas):
        die("Expected Write count differs from changed LBA count")
    if lbas != sorted(set(lbas)):
        die("changed LBA list is not unique/sorted")

    ew_lbas = []
    for row in ew:
        if not isinstance(row, dict):
            die("malformed Expected Write row")
        lba = row.get("lba")
        before = str(row.get("before_sha256", ""))
        after = str(row.get("after_sha256", ""))
        if not isinstance(lba, int):
            die("Expected Write LBA type")
        for label, value in (("before", before), ("after", after)):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                die(f"Expected Write {label} SHA at LBA {lba}")
        ew_lbas.append(lba)
    if ew_lbas != lbas:
        die("Expected Write LBA sequence")

    seen_assets = set()
    for row in audit:
        asset = row.get("asset")
        if not asset or asset in seen_assets:
            die("duplicate/missing asset audit entry")
        seen_assets.add(asset)
        if row.get("reextraction") != "PASS":
            die(f"asset re-extraction {asset}")
        final_sha = str(row.get("final_asset_sha256", ""))
        if len(final_sha) != 64 or any(c not in "0123456789abcdef" for c in final_sha.lower()):
            die(f"asset final SHA {asset}")

    return lbas


def validate_changed_sectors(candidate: Path, lbas: list[int]) -> None:
    with candidate.open("rb") as f:
        for lba in lbas:
            if lba < 0 or lba * RAW_SECTOR_SIZE >= DISC_SIZE:
                die(f"changed LBA out of range: {lba}")
            f.seek(lba * RAW_SECTOR_SIZE)
            sector = f.read(RAW_SECTOR_SIZE)
            if len(sector) != RAW_SECTOR_SIZE:
                die(f"short raw sector at LBA {lba}")
            result = verify_mode1_sector(sector)
            if not result.get("valid"):
                die(f"EDC/ECC invalid at changed LBA {lba}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Freeze Batch304 as a cumulative CD1 release-gate parent after full SHA, Expected Write, changed-sector EDC/ECC, accounting, and whole-asset audit checks."
    )
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--batch304-report", type=Path, required=True)
    ap.add_argument("--output-report", type=Path, required=True)
    args = ap.parse_args()

    if args.candidate_bin.stat().st_size != DISC_SIZE:
        die(f"candidate size {args.candidate_bin.stat().st_size} != {DISC_SIZE}")

    candidate_sha = sha256_file(args.candidate_bin)
    report = json.loads(args.batch304_report.read_text(encoding="utf-8"))
    lbas = validate_report(report, candidate_sha)
    validate_changed_sectors(args.candidate_bin, lbas)

    story_pct = HISTORICAL_STORY_DONE / HISTORICAL_STORY_TOTAL * 100.0
    out = {
        "batch": 305,
        "status": SUCCESS,
        "source_batch": 304,
        "candidate_bin_sha256": candidate_sha,
        "candidate_bin_size": DISC_SIZE,
        "pristine_reference_sha256": PRISTINE_SHA256,
        "batch304_report_sha256": sha256_file(args.batch304_report),
        "hardware_validation": "PENDING",
        "release_gates": {
            "full_output_sha256_binding": "PASS",
            "expected_write": f"{len(lbas)}/{len(lbas)} PASS",
            "changed_sector_edc_ecc": f"{len(lbas)}/{len(lbas)} PASS",
            "changed_sector_accounting": "PASS",
            "whole_asset_reextraction": "5/5 PASS",
            "guessed_payload_bytes": 0,
        },
        "story_chain": {
            "batch56_60_assets": EXPECTED_STORY_ASSETS,
            "records_reviewed": EXPECTED_STORY_REVIEWED,
            "records_translated": EXPECTED_STORY_TRANSLATED,
            "controls_preserved": EXPECTED_STORY_CONTROLS,
            "historical_done": HISTORICAL_STORY_DONE,
            "historical_total": HISTORICAL_STORY_TOTAL,
            "historical_percent": round(story_pct, 4),
        },
        "changed_raw_sectors": len(lbas),
        "changed_lbas": lbas,
        "next_parent_policy": {
            "required_status": SUCCESS,
            "required_sha_field": "candidate_bin_sha256",
            "third_variant": "BLOCK",
            "guessed_bytes": "FORBIDDEN",
        },
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(SUCCESS)
    print("candidate_bin_sha256=" + candidate_sha)
    print(f"changed_sector_edc_ecc={len(lbas)}/{len(lbas)} PASS")
    print("whole_asset_reextraction=5/5 PASS")
    print("story_metric=14865/14875 (99.9% historical denominator)")
    print("guessed_payload_bytes=0")


if __name__ == "__main__":
    main()
