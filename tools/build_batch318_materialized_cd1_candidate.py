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
PASS317 = "PASS_B317_CANONICAL_90272_SECTOR_EDCECC_LEDGER_ROUNDTRIP"
PASS318 = "PASS_B318_MATERIALIZED_CD1_CANDIDATE"
DEFAULT_BIN_NAME = "Sakura_Taisen_2_Disc1_KR_Batch309_Physical.bin"


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


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch318: materialize the authoritative Batch309 Disc 1 candidate from the exact "
            "Batch314 sparse patch, but only after Batch317 verifies all 90,272 ledger/patch "
            "records, MODE1 EDC/ECC, and the full reconstructed candidate SHA-256."
        )
    )
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--patch-file", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--output-bin-name", default=DEFAULT_BIN_NAME)
    args = ap.parse_args()

    root = args.repo_root.resolve()
    pristine = args.pristine_bin.resolve()
    patch = args.patch_file.resolve()
    ledger = args.ledger.resolve()
    outdir = args.output_dir.resolve()

    for p, label in ((pristine, "pristine BIN"), (patch, "Batch314 patch"), (ledger, "Batch316 ledger")):
        if not p.is_file():
            die(f"missing {label}: {p}")

    if sha256_file(pristine) != PRISTINE_SHA256:
        die("pristine Disc 1 SHA-256 mismatch")

    gate317 = root / "tools" / "verify_batch317_sector_ledger_edcecc_roundtrip.py"
    apply314 = root / "tools" / "batch314_raw_sector_sparse_patch.py"
    if not gate317.is_file():
        die(f"missing Batch317 gate: {gate317}")
    if not apply314.is_file():
        die(f"missing Batch314 apply tool: {apply314}")

    outdir.mkdir(parents=True, exist_ok=True)
    output_bin = outdir / args.output_bin_name
    if output_bin.exists():
        die(f"refusing to overwrite existing output: {output_bin}")

    with tempfile.TemporaryDirectory(prefix="st2_b318_") as td:
        report317 = Path(td) / "BATCH317_REPORT.json"
        run_checked(
            [
                sys.executable,
                str(gate317),
                "--patch-file", str(patch),
                "--ledger", str(ledger),
                "--pristine-bin", str(pristine),
                "--output-report", str(report317),
            ],
            "Batch317 physical roundtrip gate",
        )
        gate = json.loads(report317.read_text(encoding="utf-8"))
        if gate.get("status") != PASS317:
            die("Batch317 status mismatch")
        gates = gate.get("gates", {})
        if gates.get("ledger_patch_exact_crosscheck") != f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS":
            die("Batch317 ledger/patch exact crosscheck not fully passed")
        if gates.get("changed_sector_mode1_edc_ecc") != f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS":
            die("Batch317 MODE1 EDC/ECC not fully passed")
        if gates.get("full_candidate_roundtrip") != "PASS":
            die("Batch317 full candidate roundtrip not passed")
        if gate.get("reconstructed_candidate_sha256") != CANDIDATE_SHA256:
            die("Batch317 reconstructed candidate SHA-256 mismatch")

        cp = run_checked(
            [
                sys.executable,
                str(apply314),
                "apply",
                "--pristine-bin", str(pristine),
                "--patch-file", str(patch),
                "--output-bin", str(output_bin),
            ],
            "Batch314 exact sparse-patch apply",
        )
        if "applied_sectors=90272" not in cp.stdout:
            output_bin.unlink(missing_ok=True)
            die("Batch314 did not report 90,272 applied sectors")

        materialized_sha = sha256_file(output_bin)
        if materialized_sha != CANDIDATE_SHA256:
            output_bin.unlink(missing_ok=True)
            die("materialized candidate SHA-256 mismatch")

        report_copy = outdir / "BATCH317_PHYSICAL_GATE.json"
        shutil.copyfile(report317, report_copy)

    manifest = {
        "batch": 318,
        "status": PASS318,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate_batch": 309,
        "materialized_by": {
            "sparse_patch_batch": 314,
            "canonical_ledger_batch": 316,
            "physical_gate_batch": 317,
        },
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "estimated_or_guessed_bytes": 0,
        },
        "inputs": {
            "patch_file": patch.name,
            "patch_sha256": sha256_file(patch),
            "ledger_file": ledger.name,
            "ledger_sha256": sha256_file(ledger),
        },
        "output": {
            "bin": output_bin.name,
            "bin_sha256": materialized_sha,
            "changed_sectors_applied": EXPECTED_CHANGED,
        },
        "gates": {
            "batch317_ledger_patch_exact_crosscheck": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "batch317_changed_sector_mode1_edc_ecc": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "batch317_full_candidate_roundtrip": "PASS",
            "batch314_exact_apply": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "final_full_bin_sha256": "PASS",
            "estimated_or_guessed_bytes": 0,
        },
        "hardware_validation": "PENDING; byte-exact physical candidate is materialized, playback validation remains separate",
    }

    manifest_path = outdir / "BATCH318_MATERIALIZED_CD1_CANDIDATE.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums_path = outdir / "SHA256SUMS.txt"
    sums_path.write_text(
        f"{materialized_sha}  {output_bin.name}\n"
        f"{sha256_file(outdir / 'BATCH317_PHYSICAL_GATE.json')}  BATCH317_PHYSICAL_GATE.json\n"
        f"{sha256_file(manifest_path)}  {manifest_path.name}\n",
        encoding="utf-8",
    )

    print(PASS318)
    print(f"materialized_bin={output_bin}")
    print(f"changed_sectors_applied={EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS")
    print(f"candidate_sha256={materialized_sha}")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
