#!/usr/bin/env python3
"""Batch242 corrected Video9 promoter.

Batch240 already contains the exact B64 SK2MV_30.CAK replacement.  The original
Video10 planning tool therefore cannot be used unchanged: its no-overlap gate
would correctly reject SK2MV_30 because that footprint is already modified in
the authoritative Batch240 parent.

This corrected entry point reuses the audited raw-sector/EDC/ECC implementation
from integrate_batch241_video10_batch242.py, but replaces only the manifest
contract/cardinality.  No sector-writing primitive is duplicated or weakened.
"""
from __future__ import annotations

import json
from pathlib import Path

import integrate_batch241_video10_batch242 as core

FORMAT = "ST2-CD1-BATCH241-VIDEO9-CONSOLIDATED-MANIFEST-v2"
EXPECTED_ASSETS = 9
EXCLUDED_PARENT_ASSET = "SK2MV_30.CAK"


def load_manifest_v2(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("format") != FORMAT:
        raise SystemExit("unexpected corrected Batch241 Video9 manifest format")
    if obj.get("physical_parent_disc_sha256") != core.PARENT_SHA:
        raise SystemExit("manifest parent SHA mismatch")
    if EXCLUDED_PARENT_ASSET not in obj.get("already_promoted_in_parent", []):
        raise SystemExit("manifest does not declare Batch240-promoted SK2MV_30.CAK")

    assets = obj.get("replacement_files", [])
    if len(assets) != EXPECTED_ASSETS:
        raise SystemExit(f"expected {EXPECTED_ASSETS} remaining assets, got {len(assets)}")
    names = [Path(x["iso_path"]).name for x in assets]
    if len(names) != len(set(names)):
        raise SystemExit("duplicate asset name")
    if EXCLUDED_PARENT_ASSET in names:
        raise SystemExit("SK2MV_30.CAK is already physically present in Batch240 and must not be written again")
    return assets


def main() -> int:
    # Preserve the already-reviewed Expected Write, overlap, MODE1 EDC/ECC,
    # changed-sector accounting and whole-asset re-extraction implementation.
    core.EXPECTED_ASSETS = EXPECTED_ASSETS
    core.load_manifest = load_manifest_v2
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
