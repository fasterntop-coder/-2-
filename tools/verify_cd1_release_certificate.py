#!/usr/bin/env python3
"""Independently verify a ST2 Disc 1 release certificate.

This verifier writes no game bytes. It rejects permissive PASS substrings,
requires exact gate values, re-hashes every referenced JSON input, and optionally
binds the certificate to the supplied candidate MODE1/2352 BIN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

DISC_SIZE = 659_293_824
SOURCE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CERT_FORMAT = "ST2-CD1-RELEASE-CERTIFICATE-v1"
CERT_STATUS = "PASS_CD1_RELEASE_CERTIFICATE"
SECTOR_STATUSES = {
    "PASS_REQUIRED_LEGACY_SECTOR_PRESENT",
    "PASS_FINAL_REQUIRED_SECTORS_COMPOSED",
}
SCOPE_STATUS = "PASS_CANDIDATE_CHANGES_CONFINED_TO_91_ASSET_PLAN"
HEX = set("0123456789abcdef")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top level must be object: {path}")
    return value


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in HEX for c in value):
        raise ValueError(f"invalid lowercase SHA-256 for {label}: {value!r}")
    return value


def resolve(base: Path, recorded: Any, override: Path | None, label: str) -> Path:
    if override is not None:
        return override
    if not isinstance(recorded, str) or not recorded:
        raise ValueError(f"missing recorded path for {label}")
    path = Path(recorded)
    return path if path.is_absolute() else base / path


def verify(
    certificate_path: Path,
    *,
    plan_override: Path | None = None,
    sector_override: Path | None = None,
    scope_override: Path | None = None,
    candidate: Path | None = None,
) -> dict[str, Any]:
    cert = load(certificate_path)
    if cert.get("format") != CERT_FORMAT:
        raise ValueError("unsupported release certificate format")
    if cert.get("status") != CERT_STATUS:
        raise ValueError(f"certificate status must be exact {CERT_STATUS!r}")

    source = cert.get("source_disc")
    if not isinstance(source, dict) or source.get("size") != DISC_SIZE or source.get("sha256") != SOURCE_SHA256:
        raise ValueError("certificate pristine Disc identity mismatch")

    candidate_record = cert.get("candidate")
    if not isinstance(candidate_record, dict) or candidate_record.get("size") != DISC_SIZE:
        raise ValueError("certificate candidate size mismatch")
    candidate_sha = require_sha(candidate_record.get("sha256"), "candidate.sha256")

    gates = cert.get("gates")
    expected_gates = {
        "sha256": "PASS",
        "expected_write": "PASS",
        "mode1_2352_edc_ecc": "PASS",
        "required_legacy_sectors": "PASS",
        "write_scope": "PASS",
        "asset_reextraction": "91/91 PASS",
        "estimated_or_generated_payload_bytes": 0,
        "disc_bytes_written_by_this_tool": 0,
    }
    if not isinstance(gates, dict):
        raise ValueError("certificate gates missing")
    bad_gates = {k: (gates.get(k), v) for k, v in expected_gates.items() if gates.get(k) != v}
    if bad_gates:
        raise ValueError(f"certificate gate mismatch: {bad_gates}")

    inputs = cert.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("certificate inputs missing")
    base = certificate_path.parent
    specs = [
        ("exact_write_plan", plan_override),
        ("required_sector_result", sector_override),
        ("scope_audit_result", scope_override),
    ]
    loaded: dict[str, dict[str, Any]] = {}
    input_results = []
    for name, override in specs:
        record = inputs.get(name)
        if not isinstance(record, dict):
            raise ValueError(f"certificate input missing: {name}")
        expected_sha = require_sha(record.get("sha256"), f"inputs.{name}.sha256")
        path = resolve(base, record.get("path"), override, name)
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            raise ValueError(f"input SHA mismatch for {name}: {actual_sha} != {expected_sha}")
        loaded[name] = load(path)
        input_results.append({"name": name, "path": str(path), "sha256": actual_sha})

    plan = loaded["exact_write_plan"]
    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1" or plan.get("asset_count") != 91:
        raise ValueError("bound write plan is not the exact 91-asset plan")
    if inputs["exact_write_plan"].get("asset_count") != 91:
        raise ValueError("certificate input asset_count is not 91")

    sector = loaded["required_sector_result"]
    sector_status = sector.get("status")
    if sector_status not in SECTOR_STATUSES:
        raise ValueError(f"required-sector status not allowlisted: {sector_status!r}")
    if inputs["required_sector_result"].get("status") != sector_status:
        raise ValueError("certificate required-sector status does not match bound report")

    scope = loaded["scope_audit_result"]
    if scope.get("status") != SCOPE_STATUS:
        raise ValueError(f"scope status must be exact {SCOPE_STATUS!r}")
    if inputs["scope_audit_result"].get("status") != SCOPE_STATUS:
        raise ValueError("certificate scope status does not match bound report")
    scope_candidate = scope.get("candidate_disc")
    if not isinstance(scope_candidate, dict) or scope_candidate.get("size") != DISC_SIZE:
        raise ValueError("scope report candidate identity missing")
    if require_sha(scope_candidate.get("sha256"), "scope candidate") != candidate_sha:
        raise ValueError("scope report is not bound to certificate candidate")
    reextract = scope.get("reextraction")
    if not isinstance(reextract, dict) or reextract.get("status") != "91/91 PASS":
        raise ValueError("scope report re-extraction is not exact 91/91 PASS")
    assets = reextract.get("assets")
    if not isinstance(assets, list) or len(assets) != 91 or any(a.get("reextraction") != "PASS" for a in assets if isinstance(a, dict)):
        raise ValueError("scope report does not contain 91 PASS asset records")

    if candidate is not None:
        if candidate.stat().st_size != DISC_SIZE:
            raise ValueError("supplied candidate size mismatch")
        actual_candidate_sha = sha256_file(candidate)
        if actual_candidate_sha != candidate_sha:
            raise ValueError(f"supplied candidate SHA mismatch: {actual_candidate_sha} != {candidate_sha}")

    return {
        "batch": 212,
        "status": "PASS_CD1_RELEASE_CERTIFICATE_INDEPENDENT_VERIFICATION",
        "certificate": {"path": str(certificate_path), "sha256": sha256_file(certificate_path)},
        "candidate": {"size": DISC_SIZE, "sha256": candidate_sha, "bytes_rehashed": candidate is not None},
        "inputs": input_results,
        "gates": {"exact_status_allowlists": "PASS", "input_sha256": "PASS", "candidate_binding": "PASS", "91_asset_reextraction": "PASS"},
        "safety": {"estimated_or_generated_payload_bytes": 0, "disc_bytes_written": 0},
    }


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plan = {"format": "ST2-CD1-EXACT-WRITE-PLAN-v1", "asset_count": 91}
        sector = {"status": "PASS_REQUIRED_LEGACY_SECTOR_PRESENT"}
        assets = [{"reextraction": "PASS"} for _ in range(91)]
        candidate_sha = "1" * 64
        scope = {"status": SCOPE_STATUS, "candidate_disc": {"size": DISC_SIZE, "sha256": candidate_sha}, "reextraction": {"status": "91/91 PASS", "assets": assets}}
        paths = {}
        for name, value in (("plan", plan), ("sector", sector), ("scope", scope)):
            path = root / f"{name}.json"
            path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
            paths[name] = path
        cert = {
            "format": CERT_FORMAT,
            "status": CERT_STATUS,
            "source_disc": {"size": DISC_SIZE, "sha256": SOURCE_SHA256},
            "candidate": {"size": DISC_SIZE, "sha256": candidate_sha},
            "inputs": {
                "exact_write_plan": {"path": "plan.json", "sha256": sha256_file(paths["plan"]), "asset_count": 91},
                "required_sector_result": {"path": "sector.json", "sha256": sha256_file(paths["sector"]), "status": sector["status"]},
                "scope_audit_result": {"path": "scope.json", "sha256": sha256_file(paths["scope"]), "status": scope["status"]},
            },
            "gates": {
                "sha256": "PASS", "expected_write": "PASS", "mode1_2352_edc_ecc": "PASS",
                "required_legacy_sectors": "PASS", "write_scope": "PASS", "asset_reextraction": "91/91 PASS",
                "estimated_or_generated_payload_bytes": 0, "disc_bytes_written_by_this_tool": 0,
            },
        }
        cert_path = root / "certificate.json"
        cert_path.write_text(json.dumps(cert, sort_keys=True) + "\n", encoding="utf-8")
        verify(cert_path)
        cert["status"] = "NOT_PASS_CD1_RELEASE_CERTIFICATE"
        cert_path.write_text(json.dumps(cert, sort_keys=True) + "\n", encoding="utf-8")
        try:
            verify(cert_path)
        except ValueError:
            pass
        else:
            raise AssertionError("permissive PASS substring regression")
    print("PASS_CD1_RELEASE_CERTIFICATE_VERIFIER_SELFTEST")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--certificate", type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--required-sector-result", type=Path)
    ap.add_argument("--scope-audit-result", type=Path)
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--output", type=Path, default=Path("output/BATCH212_RELEASE_CERTIFICATE_VERIFICATION.json"))
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.certificate is None:
        ap.error("--certificate is required")
    result = verify(args.certificate, plan_override=args.plan, sector_override=args.required_sector_result, scope_override=args.scope_audit_result, candidate=args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
