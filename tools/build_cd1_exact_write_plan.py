#!/usr/bin/env python3
"""Build a deterministic, manifest-only CD1 write plan.

The plan merges the verified 58 static assets with the 33 story/movie assets,
orders all writes by LBA, and preserves only exact hash-addressed operations.
It never reads or writes copyrighted payload bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

RAW_SECTOR_SIZE = 2352
USER_SECTOR_SIZE = 2048
EXPECTED_DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
EXPECTED_DISC_SIZE = 659_293_824


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"top level must be object: {path}")
    return data


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"invalid lowercase SHA-256 for {label}: {value!r}")
    return value


def source_gate(manifest: dict[str, Any], label: str) -> None:
    source = manifest.get("source_disc")
    if not isinstance(source, dict):
        raise ValueError(f"{label}: source_disc missing")
    if source.get("size") != EXPECTED_DISC_SIZE:
        raise ValueError(f"{label}: source Disc size mismatch")
    if source.get("sha256") != EXPECTED_DISC_SHA256:
        raise ValueError(f"{label}: source Disc SHA mismatch")


def operation(scope: str, asset: dict[str, Any]) -> dict[str, Any]:
    name = asset.get("iso_path", asset.get("name"))
    if not isinstance(name, str) or not name:
        raise ValueError(f"{scope}: asset name missing")
    lba = asset.get("lba")
    size = asset.get("size")
    if not isinstance(lba, int) or isinstance(lba, bool) or lba < 0:
        raise ValueError(f"{scope}:{name}: invalid LBA")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError(f"{scope}:{name}: invalid size")
    replacement = require_sha(asset.get("replacement_sha256", asset.get("sha256")), f"{scope}:{name}:replacement")
    source_sha = asset.get("source_sha256")
    if source_sha is not None:
        source_sha = require_sha(source_sha, f"{scope}:{name}:source")
        if source_sha == replacement:
            raise ValueError(f"{scope}:{name}: source and replacement hashes are identical")
    sectors = math.ceil(size / USER_SECTOR_SIZE)
    return {
        "scope": scope,
        "asset": name.replace("\\", "/"),
        "lba": lba,
        "end_lba_exclusive": lba + sectors,
        "size": size,
        "user_sectors": sectors,
        "source_sha256": source_sha,
        "replacement_sha256": replacement,
        "source_batch": asset.get("source_batch"),
        "category": asset.get("category"),
        "group": asset.get("group"),
        "write_policy": "EXPECTED_WRITE_EXACT_HASH_ONLY",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static58", type=Path, default=Path("manifests/BATCH200_REAL_FULL58_RECOVERY.json"))
    ap.add_argument("--production", type=Path, default=Path("manifests/CD1_PRODUCTION_STORY_MOVIE_TARGETS.json"))
    ap.add_argument("--output", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    args = ap.parse_args()

    static = load(args.static58)
    production = load(args.production)
    source_gate(static, "static58")
    source_gate(production, "production")

    static_assets = static.get("assets")
    production_assets = production.get("assets")
    if not isinstance(static_assets, list) or len(static_assets) != 58:
        raise ValueError("static58 asset count must be 58")
    if not isinstance(production_assets, list) or len(production_assets) != 33:
        raise ValueError("production asset count must be 33")

    ops = [operation("static58", a) for a in static_assets] + [operation("production", a) for a in production_assets]
    ops.sort(key=lambda x: (x["lba"], x["end_lba_exclusive"], x["scope"], x["asset"]))

    seen: set[tuple[str, str]] = set()
    for op in ops:
        key = (op["scope"], op["asset"].upper())
        if key in seen:
            raise ValueError(f"duplicate operation: {key}")
        seen.add(key)
    for left, right in zip(ops, ops[1:]):
        if right["lba"] < left["end_lba_exclusive"]:
            raise ValueError(
                f"LBA overlap: {left['scope']}:{left['asset']} [{left['lba']},{left['end_lba_exclusive']}) "
                f"vs {right['scope']}:{right['asset']} [{right['lba']},{right['end_lba_exclusive']})"
            )

    plan = {
        "format": "ST2-CD1-EXACT-WRITE-PLAN-v1",
        "status": "PASS_MANIFEST_ONLY_EXACT_WRITE_PLAN",
        "source_disc": {
            "size": EXPECTED_DISC_SIZE,
            "sha256": EXPECTED_DISC_SHA256,
            "format": "MODE1/2352",
            "raw_sector_size": RAW_SECTOR_SIZE,
            "user_sector_size": USER_SECTOR_SIZE,
        },
        "input_manifests": {
            "static58": {"path": args.static58.as_posix(), "sha256": sha256_file(args.static58)},
            "production": {"path": args.production.as_posix(), "sha256": sha256_file(args.production)},
        },
        "gates": {
            "expected_write": "REQUIRED",
            "mode1_edc_ecc": "REQUIRED_AFTER_EACH_WRITE",
            "reextraction": "REQUIRED_ALL_ASSETS",
            "estimated_or_generated_payload_bytes": 0,
            "disc_bytes_written_by_this_tool": 0,
        },
        "asset_count": len(ops),
        "scope_counts": {"static58": 58, "production": 33},
        "operations": ops,
    }
    rendered = json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(hashlib.sha256(rendered.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
