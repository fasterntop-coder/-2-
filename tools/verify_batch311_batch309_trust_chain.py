#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "pristine_sha256": "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106",
    "batch308_sha256": "b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f",
    "batch309_sha256": "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01",
    "core_assets": 223,
    "supplemental_assets": 11,
    "expected_write_records": 1174,
    "supplemental_new_changed": 144,
    "cumulative_changed": 90272,
    "guessed_payload_bytes": 0,
    "third_variant_assets": 0,
    "outside_footprint_changes": 0,
}

EXPECTED_MANIFEST_STATUS = "PASS_B309_B308_PLUS_R39_UI_RUNTIME11_PHYSICAL_UNION"
EXPECTED_VERIFIER_SUCCESS = "PASS_B309_DISC_ASSET_REEXTRACTION_AND_ALL_CHANGED_SECTOR_GATE"
EXPECTED_MANIFEST_NAME = "CD1_BATCH309_B308_PLUS_R39_UI_RUNTIME11_PHYSICAL_UNION.json"
EXPECTED_VERIFIER_NAME = "verify_batch309_ui_runtime11_physical_union.py"


def fail(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_simple_constants(source: str) -> dict[str, object]:
    tree = ast.parse(source)
    out: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            out[target.id] = ast.literal_eval(node.value)
        except Exception:
            pass
    return out


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        fail(f"{label}: {actual!r} != {expected!r}")


def validate_manifest(manifest: dict) -> None:
    require_equal(manifest.get("batch"), 309, "manifest.batch")
    require_equal(manifest.get("goal"), "CD1_100_PERCENT", "manifest.goal")
    require_equal(manifest.get("status"), EXPECTED_MANIFEST_STATUS, "manifest.status")
    require_equal(manifest.get("pristine_sha256"), EXPECTED["pristine_sha256"], "manifest.pristine_sha256")

    parent = manifest.get("parent", {})
    require_equal(parent.get("batch"), 308, "manifest.parent.batch")
    require_equal(parent.get("sha256"), EXPECTED["batch308_sha256"], "manifest.parent.sha256")
    require_equal(parent.get("core_inventory"), "223/223 PASS", "manifest.parent.core_inventory")

    scope = manifest.get("scope", {})
    require_equal(scope.get("supplemental_assets"), EXPECTED["supplemental_assets"], "manifest.scope.supplemental_assets")
    require_equal(
        sum(int(scope.get(k, 0)) for k in (
            "battle_command_ui",
            "battle_visual_ui",
            "battle_font",
            "runtime_low_fonts",
            "title_assets",
        )),
        EXPECTED["supplemental_assets"],
        "manifest.scope.category_sum",
    )

    assets = manifest.get("assets", [])
    require_equal(len(assets), EXPECTED["supplemental_assets"], "manifest.assets count")
    seen_paths: set[str] = set()
    footprints: set[int] = set()
    for asset in assets:
        path = str(asset.get("path", ""))
        if not path or path in seen_paths:
            fail(f"manifest asset path duplicate/blank: {path!r}")
        seen_paths.add(path)
        lba = int(asset.get("lba", -1))
        size = int(asset.get("size", 0))
        if lba < 0 or size <= 0:
            fail(f"invalid asset geometry: {path}")
        for key in ("source_sha256", "candidate_sha256"):
            value = str(asset.get(key, ""))
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                fail(f"invalid {key}: {path}")
        sectors = (size + 2047) // 2048
        for sector in range(lba, lba + sectors):
            if sector in footprints:
                fail(f"supplemental asset LBA collision at {sector}: {path}")
            footprints.add(sector)

    require_equal(len(footprints), EXPECTED["expected_write_records"], "derived supplemental footprint sectors")

    physical = manifest.get("physical_result", {})
    checks = {
        "new_footprint_sectors": EXPECTED["expected_write_records"],
        "expected_write_records": EXPECTED["expected_write_records"],
        "new_changed_sectors": EXPECTED["supplemental_new_changed"],
        "cumulative_changed_sectors": EXPECTED["cumulative_changed"],
        "lba_collisions": 0,
        "outside_footprint_changes": EXPECTED["outside_footprint_changes"],
        "third_variant_assets": EXPECTED["third_variant_assets"],
        "guessed_payload_bytes": EXPECTED["guessed_payload_bytes"],
        "output_sha256": EXPECTED["batch309_sha256"],
    }
    for key, expected in checks.items():
        require_equal(physical.get(key), expected, f"manifest.physical_result.{key}")
    require_equal(physical.get("new_asset_reextraction"), "11/11 PASS", "manifest.physical_result.new_asset_reextraction")
    require_equal(physical.get("all_changed_sector_mode1_edc_ecc"), "90272/90272 PASS", "manifest.physical_result.all_changed_sector_mode1_edc_ecc")


def validate_verifier(source: str) -> None:
    constants = parse_simple_constants(source)
    expected_constants = {
        "PRISTINE_SHA256": EXPECTED["pristine_sha256"],
        "B308_SHA256": EXPECTED["batch308_sha256"],
        "B309_SHA256": EXPECTED["batch309_sha256"],
        "EXPECTED_CHANGED": EXPECTED["cumulative_changed"],
        "EXPECTED_ASSETS": EXPECTED["supplemental_assets"],
        "EXPECTED_FOOTPRINT_SECTORS": EXPECTED["expected_write_records"],
        "EXPECTED_NEW_CHANGED": EXPECTED["supplemental_new_changed"],
        "SUCCESS": EXPECTED_VERIFIER_SUCCESS,
    }
    for key, expected in expected_constants.items():
        require_equal(constants.get(key), expected, f"verifier constant {key}")

    required_fragments = (
        'physical.get("guessed_payload_bytes")',
        'physical.get("third_variant_assets")',
        'physical.get("outside_footprint_changes")',
        'verify_mode1_sector(b)',
        'source_sha != asset["source_sha256"]',
        'output_sha != asset["candidate_sha256"]',
    )
    for fragment in required_fragments:
        if fragment not in source:
            fail(f"Batch309 verifier lost mandatory gate fragment: {fragment}")


def validate_project_status(text: str) -> None:
    required = (
        "Core physical/static inventory: 223/223 = 100.0%",
        "Additional exact UI/runtime/title assets on current candidate: **11/11**",
        EXPECTED["batch309_sha256"],
        "cumulative changed sectors vs pristine: `90,272`",
        "all changed-sector MODE1 EDC/ECC: `90,272/90,272 PASS`",
        "guessed payload bytes: `0`",
        "third variants accepted: `0`",
        "outside-footprint changes: `0`",
    )
    for fragment in required:
        if fragment not in text:
            fail(f"PROJECT_STATUS.md missing authoritative fragment: {fragment}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch311: freeze and cross-check the Batch309 authoritative trust chain without re-analyzing already certified bytes."
    )
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-report", type=Path)
    args = parser.parse_args()

    root = args.repo_root.resolve()
    manifest_path = root / "manifests" / EXPECTED_MANIFEST_NAME
    verifier_path = root / "tools" / EXPECTED_VERIFIER_NAME
    status_path = root / "PROJECT_STATUS.md"

    for path in (manifest_path, verifier_path, status_path):
        if not path.is_file():
            fail(f"missing authoritative input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verifier_source = verifier_path.read_text(encoding="utf-8")
    project_status = status_path.read_text(encoding="utf-8")

    validate_manifest(manifest)
    validate_verifier(verifier_source)
    validate_project_status(project_status)

    report = {
        "batch": 311,
        "status": "PASS_B311_BATCH309_AUTHORITATIVE_TRUST_CHAIN_CONSISTENCY",
        "policy": "reuse previously SHA-certified physical bytes; reject metadata/tooling drift",
        "authoritative_candidate": {
            "batch": 309,
            "sha256": EXPECTED["batch309_sha256"],
            "core_inventory": "223/223 PASS",
            "supplemental_ui_runtime_title": "11/11 PASS",
            "expected_write_records": EXPECTED["expected_write_records"],
            "supplemental_new_changed_sectors": EXPECTED["supplemental_new_changed"],
            "cumulative_changed_sectors": EXPECTED["cumulative_changed"],
            "guessed_payload_bytes": 0,
            "third_variant_assets": 0,
            "outside_footprint_changes": 0,
        },
        "cross_checks": {
            "manifest": "PASS",
            "verifier_constants_and_required_gates": "PASS",
            "project_status": "PASS",
            "derived_supplemental_footprint": "1174/1174 PASS",
        },
        "input_sha256": {
            "manifest": sha256_file(manifest_path),
            "batch309_verifier": sha256_file(verifier_path),
            "project_status": sha256_file(status_path),
        },
        "physical_reverification": "NOT_REPEATED; Batch310 exact physical verifier remains the byte-level gate",
    }

    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(report["status"])
    print("candidate_sha256=" + EXPECTED["batch309_sha256"])
    print("core_inventory=223/223 PASS")
    print("supplemental_assets=11/11 PASS")
    print("derived_expected_write=1174/1174 PASS")
    print("cumulative_changed_sector_certificate=90272")


if __name__ == "__main__":
    main()
