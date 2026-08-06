#!/usr/bin/env python3
"""Preflight exact inputs for the CD1 91-asset write plan.

This tool performs no Disc writes. It scans loose files and ZIP members by exact
size and SHA-256, verifies the pristine Disc gate, and reports the precise set of
missing replacement payloads required by CD1_EXACT_WRITE_PLAN.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

EXPECTED_DISC_SIZE = 659_293_824
EXPECTED_DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CHUNK = 4 * 1024 * 1024


def sha256_stream(stream) -> str:
    h = hashlib.sha256()
    while True:
        block = stream.read(CHUNK)
        if not block:
            return h.hexdigest()
        h.update(block)


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return sha256_stream(f)


def load_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1":
        raise ValueError("unsupported write-plan format")
    if plan.get("asset_count") != 91:
        raise ValueError("write plan must contain exactly 91 assets")
    source = plan.get("source_disc", {})
    if source.get("size") != EXPECTED_DISC_SIZE or source.get("sha256") != EXPECTED_DISC_SHA256:
        raise ValueError("write plan pristine Disc gate mismatch")
    operations = plan.get("operations")
    if not isinstance(operations, list) or len(operations) != 91:
        raise ValueError("operations must contain exactly 91 entries")
    return plan


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = (p for p in root.rglob("*") if p.is_file())
        else:
            continue
        for path in candidates:
            try:
                real = path.resolve()
            except OSError:
                continue
            if real in seen:
                continue
            seen.add(real)
            yield real


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--plan", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    ap.add_argument("--output", type=Path, default=Path("output/BATCH204_PREFLIGHT_RESULT.json"))
    args = ap.parse_args()

    plan = load_plan(args.plan)
    operations = plan["operations"]

    wanted: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for op in operations:
        size = op.get("size")
        digest = op.get("replacement_sha256")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"invalid size for {op.get('asset')}")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"invalid replacement SHA for {op.get('asset')}")
        wanted[(size, digest)].append(op)

    found_payloads: dict[str, dict[str, Any]] = {}
    pristine_discs: list[dict[str, Any]] = []
    scanned_files = 0
    scanned_zip_members = 0
    errors: list[dict[str, str]] = []

    for path in iter_files(args.roots):
        scanned_files += 1
        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append({"source": str(path), "error": str(exc)})
            continue

        if size == EXPECTED_DISC_SIZE:
            try:
                digest = sha256_file(path)
                if digest == EXPECTED_DISC_SHA256:
                    pristine_discs.append({"kind": "loose", "path": str(path), "size": size, "sha256": digest})
            except OSError as exc:
                errors.append({"source": str(path), "error": str(exc)})

        candidate_hashes = [digest for candidate_size, digest in wanted if candidate_size == size]
        if candidate_hashes:
            try:
                digest = sha256_file(path)
            except OSError as exc:
                errors.append({"source": str(path), "error": str(exc)})
            else:
                if (size, digest) in wanted:
                    found_payloads.setdefault(digest, {"kind": "loose", "path": str(path), "size": size, "sha256": digest})

        if path.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    scanned_zip_members += 1
                    member_size = info.file_size
                    relevant = member_size == EXPECTED_DISC_SIZE or any(s == member_size for s, _ in wanted)
                    if not relevant:
                        continue
                    with zf.open(info) as stream:
                        digest = sha256_stream(stream)
                    locator = {"kind": "zip", "archive": str(path), "member": info.filename, "size": member_size, "sha256": digest}
                    if member_size == EXPECTED_DISC_SIZE and digest == EXPECTED_DISC_SHA256:
                        pristine_discs.append(locator)
                    if (member_size, digest) in wanted:
                        found_payloads.setdefault(digest, locator)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            errors.append({"source": str(path), "error": str(exc)})

    resolved = []
    missing = []
    for op in operations:
        digest = op["replacement_sha256"]
        entry = {
            "scope": op["scope"],
            "asset": op["asset"],
            "lba": op["lba"],
            "size": op["size"],
            "replacement_sha256": digest,
        }
        if digest in found_payloads:
            entry["source"] = found_payloads[digest]
            resolved.append(entry)
        else:
            missing.append(entry)

    status = "PASS_ALL_91_EXACT_INPUTS_READY" if pristine_discs and not missing else "BLOCKED_EXACT_INPUTS_MISSING"
    result = {
        "batch": 204,
        "status": status,
        "plan": {
            "path": args.plan.as_posix(),
            "sha256": sha256_file(args.plan),
            "asset_count": 91,
        },
        "pristine_disc": {
            "required_size": EXPECTED_DISC_SIZE,
            "required_sha256": EXPECTED_DISC_SHA256,
            "found": pristine_discs,
        },
        "replacement_inputs": {
            "resolved_count": len(resolved),
            "missing_count": len(missing),
            "resolved": resolved,
            "missing": missing,
        },
        "scan": {
            "roots": [str(p.resolve()) for p in args.roots],
            "loose_files": scanned_files,
            "zip_members": scanned_zip_members,
            "errors": errors,
        },
        "safety": {
            "estimated_payload_bytes": 0,
            "disc_bytes_written": 0,
            "selection": "EXACT_SIZE_AND_SHA256_ONLY",
            "next_required_gates": ["EXPECTED_WRITE", "MODE1_2352_EDC_ECC", "91_OF_91_REEXTRACTION"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(status)
    print(f"resolved={len(resolved)} missing={len(missing)} pristine_disc={len(pristine_discs)}")
    return 0 if status == "PASS_ALL_91_EXACT_INPUTS_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
