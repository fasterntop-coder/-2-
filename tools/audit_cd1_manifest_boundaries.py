#!/usr/bin/env python3
"""Audit Disc 1 production manifests without touching copyrighted bytes.

The gate validates manifest-only invariants before any raw-sector write:
* one canonical source Disc SHA/size/sector geometry;
* declared asset counts and category/group counts;
* SHA-256 and integer field syntax;
* unique logical asset paths/names;
* ISO user-data sector span bounds;
* no intra- or cross-manifest LBA overlap;
* Batch200 58-asset and 1,626-sector accounting;
* production story/movie 33-asset accounting.

This tool never fabricates payloads and never writes to a Disc image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SHA256_HEX_LEN = 64
EXPECTED_DISC_SIZE = 659_293_824
EXPECTED_DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
RAW_SECTOR_SIZE = 2352
USER_SECTOR_SIZE = 2048
EXPECTED_STATIC_ASSETS = 58
EXPECTED_STATIC_CHANGED_RAW_SECTORS = 1626
EXPECTED_PRODUCTION_ASSETS = 33


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"top level must be an object: {path}")
    return data


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LEN
        and all(ch in "0123456789abcdef" for ch in value)
    )


def require_int(obj: dict[str, Any], key: str, *, minimum: int = 0) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{key} must be an integer >= {minimum}, got {value!r}")
    return value


def require_sha(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not is_sha256(value):
        raise ValueError(f"{key} must be lowercase SHA-256, got {value!r}")
    return value


def canonical_source(manifest: dict[str, Any], label: str) -> tuple[int, str]:
    source = manifest.get("source_disc")
    if not isinstance(source, dict):
        raise ValueError(f"{label}: source_disc object missing")
    size = require_int(source, "size", minimum=1)
    sha = require_sha(source, "sha256")
    if size != EXPECTED_DISC_SIZE:
        raise ValueError(f"{label}: source Disc size mismatch: {size}")
    if sha != EXPECTED_DISC_SHA256:
        raise ValueError(f"{label}: source Disc SHA-256 mismatch: {sha}")
    raw_size = source.get("raw_sector_size", RAW_SECTOR_SIZE)
    if raw_size != RAW_SECTOR_SIZE:
        raise ValueError(f"{label}: raw sector size must be {RAW_SECTOR_SIZE}")
    user_size = source.get("user_size", USER_SECTOR_SIZE)
    if user_size != USER_SECTOR_SIZE:
        raise ValueError(f"{label}: user sector size must be {USER_SECTOR_SIZE}")
    return size, sha


def asset_key(asset: dict[str, Any]) -> str:
    key = asset.get("iso_path", asset.get("name"))
    if not isinstance(key, str) or not key.strip():
        raise ValueError(f"asset lacks iso_path/name: {asset!r}")
    return key.replace("\\", "/").upper()


def audit_assets(
    manifest: dict[str, Any],
    *,
    label: str,
    sha_field: str,
) -> list[dict[str, Any]]:
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError(f"{label}: assets must be a non-empty array")

    seen_keys: set[str] = set()
    spans: list[dict[str, Any]] = []
    max_lba = EXPECTED_DISC_SIZE // RAW_SECTOR_SIZE

    for index, raw_asset in enumerate(assets):
        if not isinstance(raw_asset, dict):
            raise ValueError(f"{label}: asset[{index}] must be an object")
        key = asset_key(raw_asset)
        if key in seen_keys:
            raise ValueError(f"{label}: duplicate asset key {key}")
        seen_keys.add(key)
        lba = require_int(raw_asset, "lba", minimum=0)
        size = require_int(raw_asset, "size", minimum=1)
        require_sha(raw_asset, sha_field)
        if "source_sha256" in raw_asset:
            require_sha(raw_asset, "source_sha256")
        sectors = math.ceil(size / USER_SECTOR_SIZE)
        end_lba = lba + sectors
        if end_lba > max_lba:
            raise ValueError(
                f"{label}: {key} exceeds Disc boundary: [{lba}, {end_lba}) > {max_lba}"
            )
        spans.append(
            {
                "label": label,
                "key": key,
                "lba": lba,
                "end_lba": end_lba,
                "sectors": sectors,
                "size": size,
            }
        )

    spans.sort(key=lambda item: (item["lba"], item["end_lba"], item["key"]))
    for left, right in zip(spans, spans[1:]):
        if right["lba"] < left["end_lba"]:
            raise ValueError(
                f"{label}: LBA overlap {left['key']} [{left['lba']},{left['end_lba']}) "
                f"and {right['key']} [{right['lba']},{right['end_lba']})"
            )
    return spans


def audit_production(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    canonical_source(manifest, "production")
    spans = audit_assets(manifest, label="production", sha_field="replacement_sha256")
    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("production: scope object missing")
    declared = require_int(scope, "asset_count")
    if declared != len(spans) or declared != EXPECTED_PRODUCTION_ASSETS:
        raise ValueError(
            f"production: asset_count must be {EXPECTED_PRODUCTION_ASSETS}; "
            f"declared={declared}, actual={len(spans)}"
        )
    assets = manifest["assets"]
    category_counts = Counter(asset.get("category") for asset in assets)
    if category_counts != Counter({"story": 30, "movie": 3}):
        raise ValueError(f"production: category counts mismatch: {dict(category_counts)}")
    if scope.get("story_assets") != 30 or scope.get("movie_assets") != 3:
        raise ValueError("production: scope story/movie counts mismatch")
    declared_groups = scope.get("groups")
    if not isinstance(declared_groups, dict):
        raise ValueError("production: scope.groups object missing")
    actual_groups = Counter(asset.get("group") for asset in assets)
    if dict(actual_groups) != declared_groups:
        raise ValueError(
            f"production: group counts mismatch: declared={declared_groups}, actual={dict(actual_groups)}"
        )
    return spans


def audit_static(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    canonical_source(manifest, "static58")
    spans = audit_assets(manifest, label="static58", sha_field="sha256")
    if len(spans) != EXPECTED_STATIC_ASSETS:
        raise ValueError(f"static58: expected 58 assets, got {len(spans)}")
    changed = require_int(manifest, "changed_raw_sectors")
    expected = require_int(manifest, "expected_changed_raw_sectors")
    if changed != EXPECTED_STATIC_CHANGED_RAW_SECTORS or expected != changed:
        raise ValueError(
            f"static58: changed-sector accounting mismatch: changed={changed}, expected={expected}"
        )
    if manifest.get("unregistered_changed_sectors") != 0:
        raise ValueError("static58: unregistered_changed_sectors must be 0")
    if manifest.get("sector_payload_mismatches") != 0:
        raise ValueError("static58: sector_payload_mismatches must be 0")
    if manifest.get("reextraction") != "58/58 PASS":
        raise ValueError("static58: reextraction gate is not 58/58 PASS")
    require_sha(manifest, "output_disc_sha256")
    return spans


def cross_overlap(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for a in left:
        for b in right:
            if max(a["lba"], b["lba"]) < min(a["end_lba"], b["end_lba"]):
                problems.append(
                    f"{a['label']}:{a['key']} [{a['lba']},{a['end_lba']}) overlaps "
                    f"{b['label']}:{b['key']} [{b['lba']},{b['end_lba']})"
                )
    return problems


def manifest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        type=Path,
        default=Path("manifests/CD1_PRODUCTION_STORY_MOVIE_TARGETS.json"),
    )
    parser.add_argument(
        "--static58",
        type=Path,
        default=Path("manifests/BATCH200_REAL_FULL58_RECOVERY.json"),
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        production = load_json(args.production)
        static58 = load_json(args.static58)
        production_spans = audit_production(production)
        static_spans = audit_static(static58)
        overlaps = cross_overlap(production_spans, static_spans)
        if overlaps:
            raise ValueError("cross-manifest LBA overlap:\n" + "\n".join(overlaps))
    except ValueError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    report = {
        "status": "PASS_CD1_MANIFEST_BOUNDARY_AUDIT",
        "source_disc_sha256": EXPECTED_DISC_SHA256,
        "production_manifest": {
            "path": args.production.as_posix(),
            "sha256": manifest_sha256(args.production),
            "asset_count": len(production_spans),
            "covered_user_sectors": sum(item["sectors"] for item in production_spans),
        },
        "static58_manifest": {
            "path": args.static58.as_posix(),
            "sha256": manifest_sha256(args.static58),
            "asset_count": len(static_spans),
            "covered_user_sectors": sum(item["sectors"] for item in static_spans),
            "changed_raw_sectors": EXPECTED_STATIC_CHANGED_RAW_SECTORS,
        },
        "cross_manifest_lba_overlaps": 0,
        "disc_bytes_written": 0,
        "estimated_or_generated_payload_bytes": 0,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
