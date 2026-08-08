#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PARENT_SHA = "dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83"
GATE_FORMAT = "ST2-CD1-BATCH241-VIDEO10-RECOVERY-GATE-v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_gate(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("format") != GATE_FORMAT:
        raise SystemExit(f"unexpected gate format: {obj.get('format')!r}")
    if obj.get("pristine_disc_sha256") != PRISTINE_SHA:
        raise SystemExit("gate pristine Disc SHA mismatch")
    if obj.get("physical_parent_disc_sha256") != PARENT_SHA:
        raise SystemExit("gate Batch240 parent SHA mismatch")
    if len(obj.get("legacy_packages", [])) != 3:
        raise SystemExit("gate legacy package cardinality mismatch")
    if len(obj.get("direct_candidates", [])) != 7:
        raise SystemExit("gate direct candidate cardinality mismatch")
    return obj


def audit_zip(base: Path, spec: dict) -> dict:
    path = base / spec["package"]
    row = {
        "kind": "trusted_zip",
        "name": spec["package"],
        "expected_sha256": spec["sha256"],
        "expected_asset": spec["expected_asset"],
        "expected_size": spec["size"],
        "present": path.is_file(),
        "ready": False,
    }
    if not path.is_file():
        row["status"] = "MISSING"
        return row

    actual = sha256_file(path)
    row["actual_sha256"] = actual
    if actual != spec["sha256"]:
        row["status"] = "SHA256_MISMATCH"
        return row

    expected_name = spec["expected_asset"].lower()
    matches = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if Path(info.filename).name.lower() == expected_name and info.file_size == spec["size"]:
                    matches.append(info.filename)
    except zipfile.BadZipFile:
        row["status"] = "BAD_ZIP"
        return row

    row["matching_members"] = matches
    if len(matches) != 1:
        row["status"] = "MEMBER_CONTRACT_MISMATCH"
        return row

    row["status"] = "PASS"
    row["ready"] = True
    return row


def audit_direct(base: Path, spec: dict) -> dict:
    path = base / spec["asset"]
    row = {
        "kind": "direct_candidate",
        "name": spec["asset"],
        "expected_sha256": spec["replacement_sha256"],
        "expected_size": spec["size"],
        "present": path.is_file(),
        "ready": False,
    }
    if not path.is_file():
        row["status"] = "MISSING"
        return row

    actual_size = path.stat().st_size
    row["actual_size"] = actual_size
    if actual_size != spec["size"]:
        row["status"] = "SIZE_MISMATCH"
        return row

    actual = sha256_file(path)
    row["actual_sha256"] = actual
    if actual != spec["replacement_sha256"]:
        row["status"] = "SHA256_MISMATCH"
        return row

    row["status"] = "PASS"
    row["ready"] = True
    return row


def audit_disc(path: Path | None, label: str, expected_sha256: str) -> dict:
    row = {
        "kind": "disc",
        "name": label,
        "expected_sha256": expected_sha256,
        "required_for_promotion": True,
        "ready": False,
    }
    if path is None:
        row["present"] = False
        row["status"] = "NOT_SUPPLIED"
        return row
    row["path"] = str(path)
    row["present"] = path.is_file()
    if not path.is_file():
        row["status"] = "MISSING"
        return row
    actual = sha256_file(path)
    row["actual_sha256"] = actual
    if actual != expected_sha256:
        row["status"] = "SHA256_MISMATCH"
        return row
    row["status"] = "PASS"
    row["ready"] = True
    return row


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Read-only Batch242 preflight: verify all exact Video10 inputs before recovery or raw-sector writes."
    )
    ap.add_argument("--gate", type=Path, default=Path("manifests/CD1_BATCH241_VIDEO10_RECOVERY_GATE.json"))
    ap.add_argument("--archive-dir", type=Path, required=True)
    ap.add_argument("--candidate-dir", type=Path, required=True)
    ap.add_argument("--pristine", type=Path)
    ap.add_argument("--parent", type=Path)
    ap.add_argument("--result", type=Path, default=Path("BATCH242_VIDEO10_PREFLIGHT.json"))
    args = ap.parse_args()

    gate = load_gate(args.gate)
    packages = [audit_zip(args.archive_dir, spec) for spec in gate["legacy_packages"]]
    candidates = [audit_direct(args.candidate_dir, spec) for spec in gate["direct_candidates"]]
    discs = [
        audit_disc(args.pristine, "pristine_disc1", PRISTINE_SHA),
        audit_disc(args.parent, "batch240_parent", PARENT_SHA),
    ]

    payload_rows = packages + candidates
    payload_ready = all(row["ready"] for row in payload_rows)
    disc_ready = all(row["ready"] for row in discs)
    missing_payloads = [row["name"] for row in payload_rows if row["status"] == "MISSING"]
    rejected_payloads = [
        {"name": row["name"], "status": row["status"]}
        for row in payload_rows
        if row["status"] not in {"PASS", "MISSING"}
    ]

    result = {
        "batch": 242,
        "status": "PASS_READY_FOR_EXACT_RECOVERY_AND_PROMOTION" if payload_ready and disc_ready else "BLOCKED_INPUT_PREFLIGHT",
        "read_only": True,
        "game_bytes_changed": 0,
        "guessed_payload_bytes": False,
        "payloads": {
            "required": len(payload_rows),
            "ready": sum(1 for row in payload_rows if row["ready"]),
            "missing": missing_payloads,
            "rejected": rejected_payloads,
            "items": payload_rows,
        },
        "discs": discs,
        "gates": {
            "all_payload_sha256_or_trusted_zip_contract": payload_ready,
            "pristine_sha256": discs[0]["ready"],
            "parent_sha256": discs[1]["ready"],
            "expected_write": "DEFERRED_TO_BATCH242_INTEGRATOR",
            "edc_ecc": "DEFERRED_TO_BATCH242_INTEGRATOR",
            "whole_asset_reextraction": "DEFERRED_TO_BATCH242_INTEGRATOR",
        },
        "next_command": (
            "python tools/recover_batch241_video10.py --archive-dir <archives> --candidate-dir <candidates> "
            "--output-dir BATCH241_VIDEO10_RECOVERED && "
            "python tools/integrate_batch241_video10_batch242.py --pristine <pristine.bin> "
            "--parent <batch240.bin> --candidate-dir BATCH241_VIDEO10_RECOVERED "
            "--manifest BATCH241_VIDEO10_RECOVERED/BATCH241_VIDEO10_CONSOLIDATED_MANIFEST.json"
        ) if payload_ready and disc_ready else None,
    }
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if payload_ready and disc_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
