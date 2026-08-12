#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_FILES = 1626
RAW_SECTOR_SIZE = 2352
USER_DATA_SIZE = 2048
TRACK01_SECTORS = 278_722
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
B325_PASS = "PASS_B325_FULL_ASSET_REEXTRACTION_LEDGER"
PASS = "PASS_B326_EXACT_CHANGED_ASSET_EXPECTED_WRITE_MANIFEST"


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path: Path) -> dict[str, object]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"cannot read JSON {path}: {exc}")
    if not isinstance(obj, dict):
        die(f"JSON root must be object: {path}")
    return obj


def load_ledger(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                die(f"blank ledger row at line {line_no}")
            try:
                row = json.loads(line)
            except Exception as exc:
                die(f"invalid ledger JSON line {line_no}: {exc}")
            if not isinstance(row, dict):
                die(f"ledger row {line_no} is not object")
            rows.append(row)
    if len(rows) != EXPECTED_FILES:
        die(f"ledger row count {len(rows)} != {EXPECTED_FILES}")
    return rows


def require_sha(value: object, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        die(f"invalid SHA-256 field {field}")
    try:
        bytes.fromhex(value)
    except ValueError:
        die(f"non-hex SHA-256 field {field}")
    return value.lower()


def main() -> None:
    ap = argparse.ArgumentParser(description=(
        "Batch326: consume the exact Batch325 1,626-file re-extraction ledger and report, "
        "then materialize a deterministic asset-level Expected-Write manifest containing only "
        "files whose candidate SHA differs from pristine. No guessed paths, bytes, extents, or hashes."
    ))
    ap.add_argument("--batch325-ledger", type=Path, required=True)
    ap.add_argument("--batch325-report", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    for p in (args.batch325_ledger, args.batch325_report):
        if not p.is_file():
            die(f"missing input {p}")
    if args.manifest.exists() or args.report.exists():
        die("refusing to overwrite output")

    b325 = load_json(args.batch325_report)
    if b325.get("batch") != 325 or b325.get("status") != B325_PASS:
        die("Batch325 report identity/status mismatch")
    lineage = b325.get("lineage")
    if not isinstance(lineage, dict):
        die("Batch325 lineage missing")
    if lineage.get("pristine_sha256") != PRISTINE_SHA256:
        die("Batch325 pristine lineage SHA mismatch")
    if lineage.get("candidate_sha256") != CANDIDATE_SHA256:
        die("Batch325 candidate lineage SHA mismatch")
    if lineage.get("estimated_or_guessed_bytes") != 0:
        die("Batch325 guessed-byte invariant violated")

    expected_ledger = b325.get("ledger")
    if not isinstance(expected_ledger, dict):
        die("Batch325 ledger metadata missing")
    ledger_sha = sha256_file(args.batch325_ledger)
    if expected_ledger.get("sha256") != ledger_sha:
        die("Batch325 ledger SHA mismatch")
    if expected_ledger.get("rows") != EXPECTED_FILES:
        die("Batch325 report row count mismatch")

    rows = load_ledger(args.batch325_ledger)
    changed_assets: list[dict[str, object]] = []
    unchanged = 0
    seen_paths: set[str] = set()
    previous_path: str | None = None
    full_chain = hashlib.sha256()
    changed_chain = hashlib.sha256()

    for expected_ordinal, row in enumerate(rows):
        if row.get("ordinal") != expected_ordinal:
            die(f"ordinal mismatch at row {expected_ordinal}")
        path = row.get("path")
        if not isinstance(path, str) or not path:
            die(f"invalid path at ordinal {expected_ordinal}")
        if path in seen_paths:
            die(f"duplicate path {path}")
        if previous_path is not None and path <= previous_path:
            die(f"ledger path order is not canonical: {previous_path} then {path}")
        seen_paths.add(path)
        previous_path = path

        lba = row.get("lba")
        size = row.get("size")
        flags = row.get("flags")
        changed = row.get("changed")
        if not isinstance(lba, int) or not (0 <= lba < TRACK01_SECTORS):
            die(f"invalid LBA for {path}: {lba}")
        if not isinstance(size, int) or size < 0:
            die(f"invalid size for {path}: {size}")
        if not isinstance(flags, int) or not (0 <= flags <= 255):
            die(f"invalid flags for {path}: {flags}")
        if not isinstance(changed, bool):
            die(f"invalid changed flag for {path}")
        pristine_sha = require_sha(row.get("pristine_sha256"), f"{path}.pristine_sha256")
        candidate_sha = require_sha(row.get("candidate_sha256"), f"{path}.candidate_sha256")
        if changed != (pristine_sha != candidate_sha):
            die(f"changed flag/hash relation mismatch for {path}")

        full_chain.update(canonical(row) + b"\n")
        sectors = (size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        if lba + sectors > TRACK01_SECTORS:
            die(f"asset extent exceeds Track01: {path}")

        if changed:
            expected_write = {
                "asset_ordinal": len(changed_assets),
                "source_ledger_ordinal": expected_ordinal,
                "path": path,
                "lba": lba,
                "size": size,
                "iso_user_sectors": sectors,
                "first_lba": lba,
                "last_lba": (lba + sectors - 1) if sectors else None,
                "raw_first_offset": lba * RAW_SECTOR_SIZE,
                "raw_last_sector_end_offset": (lba + sectors) * RAW_SECTOR_SIZE if sectors else lba * RAW_SECTOR_SIZE,
                "pristine_sha256": pristine_sha,
                "expected_candidate_sha256": candidate_sha,
                "expected_write_bytes": size,
                "source": "BATCH325_FULL_ASSET_REEXTRACTION_LEDGER",
                "estimated_or_guessed_bytes": 0,
            }
            changed_chain.update(canonical(expected_write) + b"\n")
            changed_assets.append(expected_write)
        else:
            unchanged += 1

    reported_reextract = b325.get("reextraction")
    if not isinstance(reported_reextract, dict):
        die("Batch325 reextraction summary missing")
    if reported_reextract.get("changed_files") != len(changed_assets):
        die("Batch325 changed-file count disagrees with ledger")
    if reported_reextract.get("unchanged_files") != unchanged:
        die("Batch325 unchanged-file count disagrees with ledger")
    if len(changed_assets) + unchanged != EXPECTED_FILES:
        die("asset accounting mismatch")
    if not changed_assets:
        die("candidate has zero changed assets; refusing meaningless manifest")

    manifest_obj = {
        "schema": "st2-disc1-batch326-exact-expected-write-manifest-v1",
        "batch": 326,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "batch325_ledger_sha256": ledger_sha,
            "estimated_or_guessed_bytes": 0,
        },
        "accounting": {
            "total_assets": EXPECTED_FILES,
            "changed_assets": len(changed_assets),
            "unchanged_assets": unchanged,
            "accounted_assets": len(changed_assets) + unchanged,
        },
        "expected_writes": changed_assets,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_bytes(json.dumps(manifest_obj, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    manifest_sha = sha256_file(args.manifest)

    report = {
        "batch": 326,
        "status": PASS,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "inputs": {
            "batch325_report": args.batch325_report.name,
            "batch325_ledger": args.batch325_ledger.name,
            "batch325_ledger_sha256": ledger_sha,
        },
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "estimated_or_guessed_bytes": 0,
        },
        "accounting": {
            "source_rows_verified": len(rows),
            "changed_assets": len(changed_assets),
            "unchanged_assets": unchanged,
            "accounted_assets": len(changed_assets) + unchanged,
            "expected_assets": EXPECTED_FILES,
        },
        "manifest": {
            "path": args.manifest.name,
            "sha256": manifest_sha,
            "expected_write_count": len(changed_assets),
            "changed_expected_write_chain_sha256": changed_chain.hexdigest(),
            "source_ledger_canonical_chain_sha256": full_chain.hexdigest(),
        },
        "gates": {
            "batch325_status": "PASS",
            "batch325_lineage": "PASS",
            "batch325_ledger_sha256": "PASS",
            "ledger_ordinals": f"{len(rows)}/{EXPECTED_FILES} PASS",
            "ledger_path_uniqueness_and_order": f"{len(rows)}/{EXPECTED_FILES} PASS",
            "hash_changed_relation": f"{len(rows)}/{EXPECTED_FILES} PASS",
            "asset_extent_bounds": f"{len(rows)}/{EXPECTED_FILES} PASS",
            "asset_accounting": f"{len(changed_assets)}+{unchanged}={EXPECTED_FILES} PASS",
            "estimated_or_guessed_bytes": 0,
        },
        "hardware_validation": "PENDING; exact asset Expected-Write scope materialization only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(PASS)
    print(f"changed_assets={len(changed_assets)} unchanged_assets={unchanged} total={EXPECTED_FILES}")
    print(f"manifest_sha256={manifest_sha}")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
