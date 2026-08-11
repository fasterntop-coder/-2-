#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED = 90_272
EXPECTED_WRITE = 1_174
CORE_ASSETS = 223
SUPPLEMENTAL_ASSETS = 11
PASS312 = "PASS_B312_BATCH309_UNIFIED_RELEASE_CANDIDATE_GATE"
PASS313 = "PASS_B313_PHYSICALLY_GATED_REPRODUCIBLE_RELEASE_BUNDLE"


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
        die(f"{label} failed: {(cp.stderr or cp.stdout).strip()}")
    return cp


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"cannot read JSON {path}: {exc}")


def assert_batch312(report: dict) -> None:
    if report.get("status") != PASS312 or report.get("release_ready") is not True:
        die("Batch312 physical release gate did not pass")
    auth = report.get("authoritative_candidate", {})
    expected = {
        "batch": 309,
        "sha256": CANDIDATE_SHA256,
        "core_assets": "223/223 PASS",
        "supplemental_assets": "11/11 PASS",
        "expected_write_records": EXPECTED_WRITE,
        "changed_sectors": EXPECTED_CHANGED,
        "guessed_payload_bytes": 0,
        "third_variant_assets": 0,
        "outside_footprint_changes": 0,
    }
    for key, value in expected.items():
        if auth.get(key) != value:
            die(f"Batch312 authoritative field drift: {key}")
    gates = report.get("gates", {})
    if gates.get("batch311_trust_chain") != "PASS":
        die("Batch311 trust chain not PASS")
    if gates.get("batch310_exact_physical") != "PASS":
        die("Batch310 physical gate not PASS")
    if gates.get("whole_asset_reextraction") != "11/11 PASS":
        die("whole-asset re-extraction not PASS")
    if gates.get("changed_sector_edc_ecc") != "90272/90272 PASS":
        die("changed-sector EDC/ECC not PASS")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch313 release-bundle materializer. It refuses to emit a release bundle until the exact "
            "Batch312 physical gate passes against the pristine Disc 1 and authoritative Batch309 candidate."
        )
    )
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument(
        "--copy-candidate",
        action="store_true",
        help="copy the SHA-certified candidate BIN into the bundle; default emits certificate material only",
    )
    args = ap.parse_args()

    root = args.repo_root.resolve()
    gate = root / "tools" / "verify_batch312_release_candidate_gate.py"
    manifest = root / "manifests" / "CD1_BATCH309_B308_PLUS_R39_UI_RUNTIME11_PHYSICAL_UNION.json"
    trust_tool = root / "tools" / "verify_batch311_batch309_trust_chain.py"
    physical_tool = root / "tools" / "verify_batch309_ui_runtime11_physical_union.py"
    for p in (gate, manifest, trust_tool, physical_tool, args.pristine_bin, args.candidate_bin):
        if not p.is_file():
            die(f"missing required input: {p}")

    if sha256_file(args.pristine_bin) != PRISTINE_SHA256:
        die("pristine Disc 1 SHA-256 mismatch")
    if sha256_file(args.candidate_bin) != CANDIDATE_SHA256:
        die("candidate Disc 1 SHA-256 mismatch")

    out = args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):
        die(f"output directory must be absent or empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="st2_batch313_") as td:
        report_path = Path(td) / "batch312_physical_release_gate.json"
        run_checked(
            [
                sys.executable,
                str(gate),
                "--repo-root",
                str(root),
                "--pristine-bin",
                str(args.pristine_bin),
                "--candidate-bin",
                str(args.candidate_bin),
                "--output-report",
                str(report_path),
                "--require-physical",
            ],
            "Batch312 physical release gate",
        )
        report = load_json(report_path)
        assert_batch312(report)
        shutil.copy2(report_path, out / "BATCH312_PHYSICAL_RELEASE_GATE.json")

    file_hashes = {
        "candidate_bin": CANDIDATE_SHA256,
        "pristine_bin": PRISTINE_SHA256,
        "batch309_manifest": sha256_file(manifest),
        "batch312_release_gate_tool": sha256_file(gate),
        "batch311_trust_chain_tool": sha256_file(trust_tool),
        "batch310_physical_union_tool": sha256_file(physical_tool),
        "batch312_physical_report": sha256_file(out / "BATCH312_PHYSICAL_RELEASE_GATE.json"),
    }

    copied_name = None
    if args.copy_candidate:
        copied_name = "Sakura_Taisen_2_Disc1_KR_Batch309.bin"
        copied = out / copied_name
        shutil.copy2(args.candidate_bin, copied)
        if sha256_file(copied) != CANDIDATE_SHA256:
            die("post-copy candidate SHA mismatch")
        file_hashes["bundled_candidate_bin"] = CANDIDATE_SHA256

    bundle = {
        "batch": 313,
        "status": PASS313,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate": {
            "lineage_batch": 309,
            "sha256": CANDIDATE_SHA256,
            "core_assets": f"{CORE_ASSETS}/{CORE_ASSETS} PASS",
            "supplemental_assets": f"{SUPPLEMENTAL_ASSETS}/{SUPPLEMENTAL_ASSETS} PASS",
            "expected_write_records": EXPECTED_WRITE,
            "changed_sectors": EXPECTED_CHANGED,
            "changed_sector_edc_ecc": "90272/90272 PASS",
            "guessed_payload_bytes": 0,
            "third_variant_assets": 0,
            "outside_footprint_changes": 0,
        },
        "release_gates": {
            "batch311_trust_chain": "PASS",
            "batch310_exact_physical": "PASS",
            "batch312_unified_release_candidate": "PASS",
            "whole_asset_reextraction": "11/11 PASS",
        },
        "bundle": {
            "candidate_included": bool(args.copy_candidate),
            "candidate_filename": copied_name,
            "physical_gate_report": "BATCH312_PHYSICAL_RELEASE_GATE.json",
            "sha256_file": "SHA256SUMS.txt",
        },
        "input_and_tool_sha256": file_hashes,
        "policy": {
            "estimated_or_guessed_bytes": "FORBIDDEN",
            "physical_gate_required": True,
            "certified_lineage_reuse": True,
        },
    }
    manifest_out = out / "BATCH313_RELEASE_BUNDLE.json"
    manifest_out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sums: list[tuple[str, str]] = [
        (sha256_file(out / "BATCH312_PHYSICAL_RELEASE_GATE.json"), "BATCH312_PHYSICAL_RELEASE_GATE.json"),
        (sha256_file(manifest_out), "BATCH313_RELEASE_BUNDLE.json"),
    ]
    if copied_name:
        sums.append((CANDIDATE_SHA256, copied_name))
    (out / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for digest, name in sorted(sums, key=lambda x: x[1])),
        encoding="ascii",
    )

    # Final self-verification: every emitted SHA line must match the emitted file.
    for line in (out / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        if sha256_file(out / name) != digest:
            die(f"bundle self-verification failed: {name}")

    print(PASS313)
    print("candidate_sha256=" + CANDIDATE_SHA256)
    print("core_assets=223/223 PASS")
    print("supplemental_assets=11/11 PASS")
    print("expected_write_records=1174")
    print("changed_sectors=90272")
    print("changed_sector_edc_ecc=90272/90272 PASS")
    print("candidate_included=" + ("YES" if args.copy_candidate else "NO"))
    print("output_dir=" + str(out))


if __name__ == "__main__":
    main()
