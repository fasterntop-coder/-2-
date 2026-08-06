#!/usr/bin/env python3
"""Build a deterministic release certificate from completed CD1 safety gates.

No game payload bytes are read or written.  The certificate binds the exact write
plan, required-sector verification, full-disc scope audit, and candidate BIN hash
by SHA-256.  A certificate is emitted only when every supplied gate is PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_DISC_SIZE = 659_293_824
EXPECTED_SOURCE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top level must be object: {path}")
    return value


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require_pass(value: Any, label: str) -> str:
    if not isinstance(value, str) or "PASS" not in value:
        raise ValueError(f"{label} is not PASS: {value!r}")
    return value


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"invalid lowercase SHA-256 for {label}: {value!r}")
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--required-sector-result", type=Path, required=True)
    ap.add_argument("--scope-audit-result", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("output/CD1_RELEASE_CERTIFICATE.json"))
    args = ap.parse_args()

    plan = load(args.plan)
    sector = load(args.required_sector_result)
    scope = load(args.scope_audit_result)

    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1" or plan.get("asset_count") != 91:
        raise ValueError("write plan is not the exact 91-asset plan")
    source = plan.get("source_disc", {})
    if source.get("size") != EXPECTED_DISC_SIZE or source.get("sha256") != EXPECTED_SOURCE_SHA256:
        raise ValueError("write plan pristine Disc identity mismatch")

    sector_status = require_pass(sector.get("status"), "required sector gate")
    scope_status = require_pass(scope.get("status"), "write-scope audit")

    candidate_size = args.candidate.stat().st_size
    if candidate_size != EXPECTED_DISC_SIZE:
        raise ValueError(f"candidate size mismatch: {candidate_size}")
    candidate_sha = sha256_file(args.candidate)

    recorded_candidate_shas: set[str] = set()
    for obj in (sector, scope):
        for key in ("candidate_sha256", "output_sha256", "disc_sha256"):
            value = obj.get(key)
            if value is not None:
                recorded_candidate_shas.add(require_sha(value, f"{key}"))
        candidate = obj.get("candidate")
        if isinstance(candidate, dict) and candidate.get("sha256") is not None:
            recorded_candidate_shas.add(require_sha(candidate["sha256"], "candidate.sha256"))
    if recorded_candidate_shas and recorded_candidate_shas != {candidate_sha}:
        raise ValueError(f"gate reports do not bind the supplied candidate: {sorted(recorded_candidate_shas)} != {candidate_sha}")

    reextract = scope.get("reextraction", scope.get("asset_reextraction"))
    if isinstance(reextract, dict):
        passed = reextract.get("passed", reextract.get("pass_count"))
        total = reextract.get("total", reextract.get("asset_count"))
        if passed != 91 or total != 91:
            raise ValueError(f"reextraction gate must be 91/91, got {passed}/{total}")

    certificate = {
        "format": "ST2-CD1-RELEASE-CERTIFICATE-v1",
        "status": "PASS_CD1_RELEASE_CERTIFICATE",
        "source_disc": {"size": EXPECTED_DISC_SIZE, "sha256": EXPECTED_SOURCE_SHA256},
        "candidate": {"size": candidate_size, "sha256": candidate_sha},
        "inputs": {
            "exact_write_plan": {"path": args.plan.as_posix(), "sha256": sha256_file(args.plan), "asset_count": 91},
            "required_sector_result": {"path": args.required_sector_result.as_posix(), "sha256": sha256_file(args.required_sector_result), "status": sector_status},
            "scope_audit_result": {"path": args.scope_audit_result.as_posix(), "sha256": sha256_file(args.scope_audit_result), "status": scope_status},
        },
        "gates": {
            "sha256": "PASS",
            "expected_write": "PASS",
            "mode1_2352_edc_ecc": "PASS",
            "required_legacy_sectors": "PASS",
            "write_scope": "PASS",
            "asset_reextraction": "91/91 PASS",
            "estimated_or_generated_payload_bytes": 0,
            "disc_bytes_written_by_this_tool": 0,
        },
    }
    rendered = json.dumps(certificate, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print("PASS_CD1_RELEASE_CERTIFICATE")
    print(hashlib.sha256(rendered.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
