#!/usr/bin/env python3
"""Bind the 91-asset plan file, asset geometry, and scope-audit records exactly.

No game bytes are generated or written. The verifier rejects a scope report that
names the right assets and hashes but substitutes the write-plan file, LBA, size,
or record geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_COUNT = 91
PLAN_FORMAT = "ST2-CD1-EXACT-WRITE-PLAN-v1"
SCOPE_STATUS = "PASS_CANDIDATE_CHANGES_CONFINED_TO_91_ASSET_PLAN"
HEX = set("0123456789abcdef")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while block := fp.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top level must be object: {path}")
    return value


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in HEX for c in value):
        raise ValueError(f"invalid lowercase SHA-256 for {label}: {value!r}")
    return value


def asset_key(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing asset name for {label}")
    return value.replace("\\", "/").upper()


def positive_int(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if value < 0 if allow_zero else value <= 0:
        raise ValueError(f"invalid {label}: {value}")
    return value


def verify(plan_path: Path, scope_path: Path) -> dict[str, Any]:
    plan = load(plan_path)
    scope = load(scope_path)
    plan_digest = sha256_file(plan_path)

    if plan.get("format") != PLAN_FORMAT or plan.get("asset_count") != EXPECTED_COUNT:
        raise ValueError("write-plan identity/count mismatch")
    operations = plan.get("operations")
    if not isinstance(operations, list) or len(operations) != EXPECTED_COUNT:
        raise ValueError("write plan must contain exactly 91 operations")

    expected: dict[str, dict[str, Any]] = {}
    for index, op in enumerate(operations):
        if not isinstance(op, dict):
            raise ValueError(f"write-plan operation {index} is not an object")
        key = asset_key(op.get("asset"), f"plan operation {index}")
        if key in expected:
            raise ValueError(f"duplicate plan asset: {op.get('asset')}")
        expected[key] = {
            "asset": op["asset"].replace("\\", "/"),
            "lba": positive_int(op.get("lba"), f"plan LBA {op.get('asset')}", allow_zero=True),
            "size": positive_int(op.get("size"), f"plan size {op.get('asset')}"),
            "replacement_sha256": require_sha(op.get("replacement_sha256"), f"plan digest {op.get('asset')}"),
        }

    if scope.get("status") != SCOPE_STATUS:
        raise ValueError("scope-audit status mismatch")
    scope_plan = scope.get("write_plan")
    if not isinstance(scope_plan, dict):
        raise ValueError("scope write_plan must be an object")
    if scope_plan.get("asset_count") != EXPECTED_COUNT:
        raise ValueError("scope write_plan asset_count mismatch")
    if require_sha(scope_plan.get("sha256"), "scope write_plan") != plan_digest:
        raise ValueError("scope report is not bound to the supplied write-plan file")

    reextraction = scope.get("reextraction")
    if not isinstance(reextraction, dict) or reextraction.get("status") != "91/91 PASS":
        raise ValueError("scope re-extraction status mismatch")
    records = reextraction.get("assets")
    if not isinstance(records, list) or len(records) != EXPECTED_COUNT:
        raise ValueError("scope must contain exactly 91 re-extraction records")

    observed: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"scope record {index} is not an object")
        if record.get("reextraction") != "PASS":
            raise ValueError(f"scope record {index} is not exact PASS")
        key = asset_key(record.get("asset"), f"scope record {index}")
        if key in observed:
            raise ValueError(f"duplicate scope asset: {record.get('asset')}")
        observed[key] = {
            "asset": record["asset"].replace("\\", "/"),
            "lba": positive_int(record.get("lba"), f"scope LBA {record.get('asset')}", allow_zero=True),
            "size": positive_int(record.get("size"), f"scope size {record.get('asset')}"),
            "replacement_sha256": require_sha(record.get("replacement_sha256"), f"scope digest {record.get('asset')}"),
        }

    if set(expected) != set(observed):
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        raise ValueError(f"asset-set mismatch: missing={missing} extra={extra}")

    verified = []
    for key in sorted(expected):
        exp = expected[key]
        got = observed[key]
        for field in ("lba", "size", "replacement_sha256"):
            if got[field] != exp[field]:
                raise ValueError(
                    f"{field} mismatch for {exp['asset']}: expected={exp[field]!r} observed={got[field]!r}"
                )
        verified.append({**exp, "geometry_binding": "PASS"})

    return {
        "batch": 215,
        "status": "PASS_91_ASSET_PLAN_SCOPE_GEOMETRY_BINDING",
        "plan": {"path": plan_path.as_posix(), "sha256": plan_digest, "asset_count": EXPECTED_COUNT},
        "scope_audit": {"path": scope_path.as_posix(), "sha256": sha256_file(scope_path)},
        "verified_asset_count": len(verified),
        "assets": verified,
        "gates": {
            "plan_file_sha256_binding": "PASS",
            "asset_set_bijection": "PASS",
            "lba_equality": "PASS",
            "size_equality": "PASS",
            "replacement_sha256_equality": "PASS",
        },
        "safety": {"estimated_or_generated_payload_bytes": 0, "disc_bytes_written": 0},
    }


def selftest() -> None:
    import tempfile

    operations = []
    records = []
    for i in range(EXPECTED_COUNT):
        digest = f"{i + 1:064x}"[-64:]
        asset = f"SAKURA1/A{i:02d}.BIN"
        op = {"asset": asset, "lba": 1000 + i * 2, "size": 2048 + i, "replacement_sha256": digest}
        operations.append(op)
        records.append({**op, "reextraction": "PASS"})
    plan = {"format": PLAN_FORMAT, "asset_count": EXPECTED_COUNT, "operations": operations}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan_path = root / "plan.json"
        scope_path = root / "scope.json"
        plan_path.write_text(json.dumps(plan, sort_keys=True) + "\n", encoding="utf-8")
        scope = {
            "status": SCOPE_STATUS,
            "write_plan": {"sha256": sha256_file(plan_path), "asset_count": EXPECTED_COUNT},
            "reextraction": {"status": "91/91 PASS", "assets": records},
        }
        scope_path.write_text(json.dumps(scope, sort_keys=True) + "\n", encoding="utf-8")
        assert verify(plan_path, scope_path)["verified_asset_count"] == EXPECTED_COUNT

        bad = json.loads(json.dumps(scope))
        bad["reextraction"]["assets"][4]["lba"] += 1
        scope_path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
        try:
            verify(plan_path, scope_path)
        except ValueError:
            pass
        else:
            raise AssertionError("LBA substitution was accepted")

        bad = json.loads(json.dumps(scope))
        bad["reextraction"]["assets"][5]["size"] += 1
        scope_path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
        try:
            verify(plan_path, scope_path)
        except ValueError:
            pass
        else:
            raise AssertionError("size substitution was accepted")

        bad = json.loads(json.dumps(scope))
        bad["write_plan"]["sha256"] = "0" * 64
        scope_path.write_text(json.dumps(bad, sort_keys=True) + "\n", encoding="utf-8")
        try:
            verify(plan_path, scope_path)
        except ValueError:
            pass
        else:
            raise AssertionError("write-plan SHA substitution was accepted")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--scope-audit", type=Path)
    ap.add_argument("--output", type=Path, default=Path("output/BATCH215_PLAN_SCOPE_GEOMETRY_BINDING.json"))
    args = ap.parse_args()
    if args.selftest:
        selftest()
        print("PASS_91_ASSET_PLAN_SCOPE_GEOMETRY_BINDING_SELFTEST")
        return 0
    if args.plan is None or args.scope_audit is None:
        ap.error("--plan and --scope-audit are required")
    result = verify(args.plan, args.scope_audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
