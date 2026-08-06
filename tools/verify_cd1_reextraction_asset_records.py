#!/usr/bin/env python3
"""Strictly verify the 91 per-asset re-extraction records in a CD1 scope audit.

This closes a type-filtering gap where non-object entries could be skipped by a
permissive generator expression. No game bytes are read or written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_COUNT = 91
EXPECTED_SCOPE_STATUS = "PASS_CANDIDATE_CHANGES_CONFINED_TO_91_ASSET_PLAN"
EXPECTED_REEXTRACTION_STATUS = "91/91 PASS"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("scope audit top level must be an object")
    return value


def verify(scope: dict[str, Any]) -> dict[str, Any]:
    if scope.get("status") != EXPECTED_SCOPE_STATUS:
        raise ValueError("scope audit status mismatch")
    reextraction = scope.get("reextraction")
    if not isinstance(reextraction, dict):
        raise ValueError("reextraction object missing")
    if reextraction.get("status") != EXPECTED_REEXTRACTION_STATUS:
        raise ValueError("reextraction status mismatch")
    assets = reextraction.get("assets")
    if not isinstance(assets, list) or len(assets) != EXPECTED_COUNT:
        raise ValueError("reextraction assets must be a 91-entry list")

    names: set[str] = set()
    checked = []
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            raise ValueError(f"asset record {index} is not an object")
        if asset.get("reextraction") != "PASS":
            raise ValueError(f"asset record {index} is not exact PASS")
        name = asset.get("asset")
        if not isinstance(name, str) or not name:
            raise ValueError(f"asset record {index} has no asset name")
        key = name.replace("\\", "/").upper()
        if key in names:
            raise ValueError(f"duplicate asset record: {name}")
        names.add(key)
        digest = asset.get("replacement_sha256", asset.get("sha256"))
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"asset record {index} has invalid SHA-256")
        checked.append({"asset": name, "sha256": digest, "reextraction": "PASS"})

    return {
        "batch": 213,
        "status": "PASS_STRICT_91_ASSET_REEXTRACTION_RECORDS",
        "asset_count": EXPECTED_COUNT,
        "unique_asset_count": len(names),
        "assets": checked,
        "safety": {"estimated_or_generated_payload_bytes": 0, "disc_bytes_written": 0},
    }


def selftest() -> None:
    assets = [{"asset": f"A/{i:02d}.BIN", "replacement_sha256": f"{i:064x}"[-64:], "reextraction": "PASS"} for i in range(EXPECTED_COUNT)]
    scope = {"status": EXPECTED_SCOPE_STATUS, "reextraction": {"status": EXPECTED_REEXTRACTION_STATUS, "assets": assets}}
    assert verify(scope)["asset_count"] == EXPECTED_COUNT
    bad = json.loads(json.dumps(scope))
    bad["reextraction"]["assets"][17] = "PASS"
    try:
        verify(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("non-object asset record was accepted")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--scope-audit", type=Path)
    ap.add_argument("--output", type=Path, default=Path("output/BATCH213_STRICT_REEXTRACTION_RECORDS.json"))
    args = ap.parse_args()
    if args.selftest:
        selftest()
        print("PASS_STRICT_91_ASSET_REEXTRACTION_SELFTEST")
        return 0
    if args.scope_audit is None:
        ap.error("--scope-audit is required")
    result = verify(load(args.scope_audit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
