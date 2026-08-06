#!/usr/bin/env python3
"""Verify a strict one-to-one binding between the 91-asset write plan and re-extraction records.

This tool reads no game payload bytes and performs no Disc writes. It rejects
missing, extra, duplicate, renamed, or hash-substituted re-extraction records.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_COUNT = 91
PLAN_FORMAT = "ST2-CD1-EXACT-WRITE-PLAN-v1"
SCOPE_STATUS = "PASS_CANDIDATE_CHANGES_CONFINED_TO_91_ASSET_PLAN"
REEXTRACTION_STATUS = "91/91 PASS"
HEX = set("0123456789abcdef")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top level must be object: {path}")
    return value


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in HEX for c in value):
        raise ValueError(f"invalid lowercase SHA-256 for {label}: {value!r}")
    return value


def key(name: Any, label: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError(f"missing asset name for {label}")
    return name.replace("\\", "/").upper()


def verify(plan: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    if plan.get("format") != PLAN_FORMAT or plan.get("asset_count") != EXPECTED_COUNT:
        raise ValueError("write plan identity/count mismatch")
    operations = plan.get("operations")
    if not isinstance(operations, list) or len(operations) != EXPECTED_COUNT:
        raise ValueError("write plan operations must contain exactly 91 objects")

    expected: dict[str, dict[str, Any]] = {}
    for index, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ValueError(f"write-plan operation {index} is not an object")
        asset_key = key(op.get("asset"), f"write-plan operation {index}")
        if asset_key in expected:
            raise ValueError(f"duplicate write-plan asset: {op.get('asset')}")
        expected[asset_key] = {
            "asset": op["asset"].replace("\\", "/"),
            "replacement_sha256": require_sha(op.get("replacement_sha256"), f"plan:{op.get('asset')}"),
            "lba": op.get("lba"),
            "size": op.get("size"),
        }

    if scope.get("status") != SCOPE_STATUS:
        raise ValueError("scope audit status mismatch")
    reextraction = scope.get("reextraction")
    if not isinstance(reextraction, dict) or reextraction.get("status") != REEXTRACTION_STATUS:
        raise ValueError("scope re-extraction status mismatch")
    assets = reextraction.get("assets")
    if not isinstance(assets, list) or len(assets) != EXPECTED_COUNT:
        raise ValueError("scope re-extraction assets must contain exactly 91 objects")

    observed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(assets):
        if not isinstance(record, dict):
            raise ValueError(f"re-extraction record {index} is not an object")
        if record.get("reextraction") != "PASS":
            raise ValueError(f"re-extraction record {index} is not exact PASS")
        asset_key = key(record.get("asset"), f"re-extraction record {index}")
        if asset_key in observed:
            raise ValueError(f"duplicate re-extraction asset: {record.get('asset')}")
        digest = require_sha(record.get("replacement_sha256", record.get("sha256")), f"scope:{record.get('asset')}")
        observed[asset_key] = {"asset": record["asset"].replace("\\", "/"), "replacement_sha256": digest}

    missing = sorted(set(expected) - set(observed))
    extra = sorted(set(observed) - set(expected))
    if missing or extra:
        raise ValueError(f"plan/re-extraction asset-set mismatch: missing={missing} extra={extra}")

    mismatched = []
    verified = []
    for asset_key in sorted(expected):
        exp = expected[asset_key]
        got = observed[asset_key]
        if got["replacement_sha256"] != exp["replacement_sha256"]:
            mismatched.append({"asset": exp["asset"], "expected": exp["replacement_sha256"], "observed": got["replacement_sha256"]})
        else:
            verified.append({"asset": exp["asset"], "lba": exp["lba"], "size": exp["size"], "replacement_sha256": exp["replacement_sha256"], "reextraction": "PASS"})
    if mismatched:
        raise ValueError(f"replacement SHA mismatch: {mismatched}")

    return {
        "batch": 214,
        "status": "PASS_91_ASSET_PLAN_REEXTRACTION_BIJECTION",
        "asset_count": EXPECTED_COUNT,
        "plan_unique_assets": len(expected),
        "reextraction_unique_assets": len(observed),
        "assets": verified,
        "gates": {"asset_set_equality": "PASS", "replacement_sha256_equality": "PASS", "exact_pass_status": "PASS"},
        "safety": {"estimated_or_generated_payload_bytes": 0, "disc_bytes_written": 0},
    }


def selftest() -> None:
    operations = []
    records = []
    for i in range(EXPECTED_COUNT):
        digest = f"{i + 1:064x}"[-64:]
        name = f"SAKURA1/A{i:02d}.BIN"
        operations.append({"asset": name, "lba": 1000 + i, "size": 2048, "replacement_sha256": digest})
        records.append({"asset": name, "replacement_sha256": digest, "reextraction": "PASS"})
    plan = {"format": PLAN_FORMAT, "asset_count": EXPECTED_COUNT, "operations": operations}
    scope = {"status": SCOPE_STATUS, "reextraction": {"status": REEXTRACTION_STATUS, "assets": records}}
    assert verify(plan, scope)["asset_count"] == EXPECTED_COUNT

    bad = json.loads(json.dumps(scope))
    bad["reextraction"]["assets"][7]["replacement_sha256"] = "f" * 64
    try:
        verify(plan, bad)
    except ValueError:
        pass
    else:
        raise AssertionError("hash substitution was accepted")

    bad = json.loads(json.dumps(scope))
    bad["reextraction"]["assets"][7]["asset"] = "SAKURA1/EXTRA.BIN"
    try:
        verify(plan, bad)
    except ValueError:
        pass
    else:
        raise AssertionError("asset substitution was accepted")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--scope-audit", type=Path)
    ap.add_argument("--output", type=Path, default=Path("output/BATCH214_PLAN_REEXTRACTION_BIJECTION.json"))
    args = ap.parse_args()
    if args.selftest:
        selftest()
        print("PASS_91_ASSET_PLAN_REEXTRACTION_BIJECTION_SELFTEST")
        return 0
    if args.plan is None or args.scope_audit is None:
        ap.error("--plan and --scope-audit are required")
    result = verify(load(args.plan), load(args.scope_audit))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
