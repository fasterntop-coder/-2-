#!/usr/bin/env python3
"""Bind Batch204 replacement inputs to the 91-asset exact write plan.

No Disc bytes are written. Each resolved input must map to exactly one plan
operation by asset name, size and replacement SHA-256. Duplicate locators,
missing records, extra records and digest aliasing are rejected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"top-level object required: {path}")
    return obj


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"invalid SHA-256 for {label}: {value!r}")
    return value


def locator_key(source: dict[str, Any]) -> tuple[str, ...]:
    kind = source.get("kind")
    if kind == "loose":
        path = source.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("loose source path missing")
        return ("loose", path)
    if kind == "zip":
        archive, member = source.get("archive"), source.get("member")
        if not isinstance(archive, str) or not archive or not isinstance(member, str) or not member:
            raise ValueError("zip source archive/member missing")
        return ("zip", archive, member)
    raise ValueError(f"unsupported source kind: {kind!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    ap.add_argument("--preflight", type=Path, default=Path("output/BATCH204_PREFLIGHT_RESULT.json"))
    ap.add_argument("--output", type=Path, default=Path("output/BATCH217_REPLACEMENT_BINDING.json"))
    args = ap.parse_args()

    plan = load(args.plan)
    preflight = load(args.preflight)
    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1" or plan.get("asset_count") != 91:
        raise ValueError("unsupported or incomplete 91-asset plan")
    if preflight.get("status") != "PASS_ALL_91_EXACT_INPUTS_READY":
        raise ValueError("preflight is not PASS_ALL_91_EXACT_INPUTS_READY")

    operations = plan.get("operations")
    resolved = preflight.get("replacement_inputs", {}).get("resolved")
    missing = preflight.get("replacement_inputs", {}).get("missing")
    if not isinstance(operations, list) or len(operations) != 91:
        raise ValueError("plan operations must contain 91 records")
    if not isinstance(resolved, list) or len(resolved) != 91 or missing != []:
        raise ValueError("preflight must contain exactly 91 resolved records and zero missing")

    plan_map: dict[str, dict[str, Any]] = {}
    digest_to_assets: dict[str, list[str]] = {}
    for op in operations:
        if not isinstance(op, dict):
            raise ValueError("non-object plan operation")
        asset = op.get("asset")
        if not isinstance(asset, str) or not asset or asset in plan_map:
            raise ValueError(f"invalid or duplicate plan asset: {asset!r}")
        digest = require_sha(op.get("replacement_sha256"), f"plan:{asset}")
        size = op.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"invalid plan size: {asset}")
        plan_map[asset] = op
        digest_to_assets.setdefault(digest, []).append(asset)

    seen_assets: set[str] = set()
    seen_locators: dict[tuple[str, ...], str] = {}
    bindings: list[dict[str, Any]] = []
    for rec in resolved:
        if not isinstance(rec, dict):
            raise ValueError("non-object resolved record")
        asset = rec.get("asset")
        if asset not in plan_map or asset in seen_assets:
            raise ValueError(f"unknown or duplicate resolved asset: {asset!r}")
        op = plan_map[asset]
        digest = require_sha(rec.get("replacement_sha256"), f"resolved:{asset}")
        source = rec.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"resolved source missing: {asset}")
        source_digest = require_sha(source.get("sha256"), f"source:{asset}")
        if digest != op["replacement_sha256"] or source_digest != digest:
            raise ValueError(f"replacement SHA mismatch: {asset}")
        if rec.get("size") != op["size"] or source.get("size") != op["size"]:
            raise ValueError(f"replacement size mismatch: {asset}")
        if rec.get("lba") != op["lba"] or rec.get("scope") != op["scope"]:
            raise ValueError(f"replacement geometry mismatch: {asset}")
        key = locator_key(source)
        previous = seen_locators.get(key)
        if previous is not None and previous != digest:
            raise ValueError(f"one locator claims multiple payload hashes: {key}")
        seen_locators[key] = digest
        seen_assets.add(asset)
        bindings.append({
            "asset": asset,
            "scope": op["scope"],
            "lba": op["lba"],
            "size": op["size"],
            "replacement_sha256": digest,
            "source": source,
            "digest_alias_asset_count": len(digest_to_assets[digest]),
            "status": "PASS_EXACT_SIZE_SHA_GEOMETRY_BINDING",
        })

    if seen_assets != set(plan_map):
        raise ValueError("resolved asset set is not a bijection with the plan")

    result = {
        "batch": 217,
        "status": "PASS_91_OF_91_REPLACEMENT_INPUT_BINDING",
        "plan": {"path": args.plan.as_posix(), "sha256": sha256_file(args.plan)},
        "preflight": {"path": args.preflight.as_posix(), "sha256": sha256_file(args.preflight)},
        "asset_count": 91,
        "unique_locator_count": len(seen_locators),
        "bindings": sorted(bindings, key=lambda x: (x["lba"], x["asset"])),
        "safety": {
            "selection": "EXACT_SIZE_SHA256_AND_PLAN_GEOMETRY",
            "estimated_payload_bytes": 0,
            "disc_bytes_written": 0,
            "next_gates": ["EXPECTED_WRITE", "MODE1_2352_EDC_ECC", "91_OF_91_REEXTRACTION"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
