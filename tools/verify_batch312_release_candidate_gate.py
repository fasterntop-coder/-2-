#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BATCH309_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
EXPECTED_CHANGED = 90_272
EXPECTED_WRITE = 1_174
CORE_ASSETS = 223
SUPPLEMENTAL_ASSETS = 11
SUCCESS = "PASS_B312_BATCH309_UNIFIED_RELEASE_CANDIDATE_GATE"


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_checked(cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(cmd, text=True, capture_output=True)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout).strip()
        die(f"{label} failed: {detail}")
    return cp


def load_json(path: Path, label: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"cannot load {label}: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch312 unified Disc1 gate. Always runs the Batch311 trust-chain check; "
            "when pristine/candidate BINs are supplied, also runs the Batch310 exact physical gate "
            "and binds both results into one release-candidate certificate."
        )
    )
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--pristine-bin", type=Path)
    ap.add_argument("--candidate-bin", type=Path)
    ap.add_argument("--output-report", type=Path, required=True)
    ap.add_argument(
        "--require-physical",
        action="store_true",
        help="fail unless both BINs are supplied and the exact Batch310 byte-level gate passes",
    )
    args = ap.parse_args()

    root = args.repo_root.resolve()
    trust_tool = root / "tools" / "verify_batch311_batch309_trust_chain.py"
    physical_tool = root / "tools" / "verify_batch309_ui_runtime11_physical_union.py"
    manifest = root / "manifests" / "CD1_BATCH309_B308_PLUS_R39_UI_RUNTIME11_PHYSICAL_UNION.json"

    for p in (trust_tool, physical_tool, manifest):
        if not p.is_file():
            die(f"missing authoritative input: {p}")

    bins = (args.pristine_bin, args.candidate_bin)
    if (bins[0] is None) != (bins[1] is None):
        die("--pristine-bin and --candidate-bin must be supplied together")
    physical_requested = bins[0] is not None
    if args.require_physical and not physical_requested:
        die("--require-physical requires both BIN inputs")

    with tempfile.TemporaryDirectory(prefix="st2_batch312_") as td:
        tmp = Path(td)
        trust_report_path = tmp / "batch311_trust.json"
        run_checked(
            [
                sys.executable,
                str(trust_tool),
                "--repo-root",
                str(root),
                "--output-report",
                str(trust_report_path),
            ],
            "Batch311 trust-chain gate",
        )
        trust = load_json(trust_report_path, "Batch311 trust report")
        if trust.get("status") != "PASS_B311_BATCH309_AUTHORITATIVE_TRUST_CHAIN_CONSISTENCY":
            die("unexpected Batch311 trust status")

        authoritative = trust.get("authoritative_candidate", {})
        exact = {
            "sha256": BATCH309_SHA256,
            "core_inventory": "223/223 PASS",
            "supplemental_ui_runtime_title": "11/11 PASS",
            "expected_write_records": EXPECTED_WRITE,
            "cumulative_changed_sectors": EXPECTED_CHANGED,
            "guessed_payload_bytes": 0,
            "third_variant_assets": 0,
            "outside_footprint_changes": 0,
        }
        for key, expected in exact.items():
            if authoritative.get(key) != expected:
                die(f"Batch311 authoritative field drift: {key}")

        physical: dict | None = None
        if physical_requested:
            assert args.pristine_bin is not None and args.candidate_bin is not None
            for p in (args.pristine_bin, args.candidate_bin):
                if not p.is_file():
                    die(f"missing BIN input: {p}")

            physical_report_path = tmp / "batch310_physical.json"
            run_checked(
                [
                    sys.executable,
                    str(physical_tool),
                    "--pristine-bin",
                    str(args.pristine_bin),
                    "--candidate-bin",
                    str(args.candidate_bin),
                    "--manifest",
                    str(manifest),
                    "--output-report",
                    str(physical_report_path),
                ],
                "Batch310 exact physical gate",
            )
            physical = load_json(physical_report_path, "Batch310 physical report")
            if physical.get("status") != "PASS_B309_DISC_ASSET_REEXTRACTION_AND_ALL_CHANGED_SECTOR_GATE":
                die("unexpected Batch310 physical status")
            if physical.get("pristine_sha256") != PRISTINE_SHA256:
                die("physical pristine SHA drift")
            if physical.get("candidate_sha256") != BATCH309_SHA256:
                die("physical candidate SHA drift")
            if physical.get("changed_sector_count") != EXPECTED_CHANGED:
                die("physical changed-sector accounting drift")
            if physical.get("expected_write_records_certificate") != EXPECTED_WRITE:
                die("physical expected-write drift")
            if physical.get("supplemental_assets_reextracted") != "11/11 PASS":
                die("physical supplemental re-extraction drift")
            if physical.get("changed_sector_edc_ecc") != "90272/90272 PASS":
                die("physical EDC/ECC drift")
            if physical.get("guessed_payload_bytes") != 0:
                die("guessed payload bytes are forbidden")

            # Bind certificate to the exact files presented in this invocation.
            if sha256_file(args.pristine_bin) != PRISTINE_SHA256:
                die("post-gate pristine SHA mismatch")
            if sha256_file(args.candidate_bin) != BATCH309_SHA256:
                die("post-gate candidate SHA mismatch")

        report = {
            "batch": 312,
            "status": SUCCESS if physical_requested else "PASS_B312_TRUST_ONLY_PHYSICAL_NOT_RUN",
            "goal": "CD1_100_PERCENT",
            "authoritative_candidate": {
                "batch": 309,
                "sha256": BATCH309_SHA256,
                "core_assets": f"{CORE_ASSETS}/{CORE_ASSETS} PASS",
                "supplemental_assets": f"{SUPPLEMENTAL_ASSETS}/{SUPPLEMENTAL_ASSETS} PASS",
                "expected_write_records": EXPECTED_WRITE,
                "changed_sectors": EXPECTED_CHANGED,
                "guessed_payload_bytes": 0,
                "third_variant_assets": 0,
                "outside_footprint_changes": 0,
            },
            "gates": {
                "batch311_trust_chain": "PASS",
                "batch310_exact_physical": "PASS" if physical_requested else "NOT_RUN",
                "whole_asset_reextraction": "11/11 PASS" if physical_requested else "CERTIFIED_BY_BATCH311_CHAIN",
                "changed_sector_edc_ecc": "90272/90272 PASS" if physical_requested else "CERTIFIED_BY_BATCH311_CHAIN",
            },
            "policy": {
                "estimated_or_guessed_bytes": "FORBIDDEN",
                "sha_certified_bytes": "REUSE_ALLOWED",
                "release_ready_requires_physical": True,
            },
            "release_ready": bool(physical_requested),
        }
        if physical_requested:
            report["input_sha256"] = {
                "pristine_bin": PRISTINE_SHA256,
                "candidate_bin": BATCH309_SHA256,
                "manifest": sha256_file(manifest),
                "batch311_tool": sha256_file(trust_tool),
                "batch310_tool": sha256_file(physical_tool),
            }

        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(report["status"])
    print("candidate_sha256=" + BATCH309_SHA256)
    print("core_assets=223/223 PASS")
    print("supplemental_assets=11/11 PASS")
    print("physical_gate=" + ("PASS" if physical_requested else "NOT_RUN"))
    print("release_ready=" + ("YES" if physical_requested else "NO"))


if __name__ == "__main__":
    main()
