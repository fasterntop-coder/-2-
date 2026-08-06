#!/usr/bin/env python3
"""Materialize the 91 SHA-bound CD1 replacement payloads into a clean staging tree.

Consumes Batch217's exact input binding. Every loose file or ZIP member is read
again, checked against the bound size and SHA-256, and written atomically under
an asset-derived filename. No Disc image is opened or modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

SAFE_ASSET = re.compile(r"^[A-Za-z0-9_.-]+$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"top-level JSON object required: {path}")
    return obj


def resolve_under(root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=True)
    root_resolved = root.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} escapes input root: {value}") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} is not a regular file: {value}")
    return resolved


def read_bound_payload(source: dict[str, Any], input_root: Path) -> tuple[bytes, dict[str, str]]:
    kind = source.get("kind")
    if kind == "loose":
        value = source.get("path")
        if not isinstance(value, str) or not value:
            raise ValueError("loose source path missing")
        path = resolve_under(input_root, value, "loose source")
        return path.read_bytes(), {"kind": "loose", "path": value}

    if kind == "zip":
        archive_value, member = source.get("archive"), source.get("member")
        if not isinstance(archive_value, str) or not archive_value:
            raise ValueError("ZIP archive path missing")
        if not isinstance(member, str) or not member:
            raise ValueError("ZIP member missing")
        member_path = PurePosixPath(member)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"unsafe ZIP member path: {member}")
        archive = resolve_under(input_root, archive_value, "ZIP archive")
        with zipfile.ZipFile(archive, "r") as zf:
            infos = [i for i in zf.infolist() if i.filename == member and not i.is_dir()]
            if len(infos) != 1:
                raise ValueError(f"ZIP member must resolve exactly once: {archive_value}!{member}")
            data = zf.read(infos[0])
        return data, {"kind": "zip", "archive": archive_value, "member": member}

    raise ValueError(f"unsupported source kind: {kind!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--binding", type=Path, default=Path("output/BATCH217_REPLACEMENT_BINDING.json"))
    ap.add_argument("--input-root", type=Path, default=Path("."))
    ap.add_argument("--stage-dir", type=Path, default=Path("output/CD1_BOUND_REPLACEMENTS"))
    ap.add_argument("--manifest", type=Path, default=Path("output/BATCH218_MATERIALIZED_REPLACEMENTS.json"))
    args = ap.parse_args()

    binding = load_object(args.binding)
    if binding.get("status") != "PASS_91_OF_91_REPLACEMENT_INPUT_BINDING" or binding.get("asset_count") != 91:
        raise ValueError("Batch217 binding is not a complete 91-asset PASS")
    bindings = binding.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != 91:
        raise ValueError("binding must contain exactly 91 records")

    target_parent = args.stage_dir.parent.resolve()
    target_parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".cd1-bound-", dir=target_parent))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for rec in bindings:
            if not isinstance(rec, dict):
                raise ValueError("non-object binding record")
            asset = rec.get("asset")
            if not isinstance(asset, str) or not SAFE_ASSET.fullmatch(asset) or asset in seen:
                raise ValueError(f"unsafe or duplicate asset name: {asset!r}")
            expected_size = rec.get("size")
            expected_sha = rec.get("replacement_sha256")
            source = rec.get("source")
            if not isinstance(expected_size, int) or isinstance(expected_size, bool) or expected_size <= 0:
                raise ValueError(f"invalid expected size: {asset}")
            if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                raise ValueError(f"invalid expected SHA-256: {asset}")
            if not isinstance(source, dict):
                raise ValueError(f"missing source object: {asset}")

            data, source_summary = read_bound_payload(source, args.input_root)
            actual_sha = sha256_bytes(data)
            if len(data) != expected_size or actual_sha != expected_sha:
                raise ValueError(
                    f"bound payload mismatch: {asset}: size {len(data)}/{expected_size}, "
                    f"sha256 {actual_sha}/{expected_sha}"
                )

            out_name = f"{asset}.bin"
            out_path = tmp / out_name
            out_path.write_bytes(data)
            if out_path.stat().st_size != expected_size or sha256_file(out_path) != expected_sha:
                raise ValueError(f"post-write staging verification failed: {asset}")
            seen.add(asset)
            rows.append({
                "asset": asset,
                "scope": rec.get("scope"),
                "lba": rec.get("lba"),
                "size": expected_size,
                "sha256": expected_sha,
                "staged_file": out_name,
                "source": source_summary,
                "status": "PASS_RE_READ_SIZE_SHA256_POST_WRITE",
            })

        if len(seen) != 91:
            raise ValueError("materialized asset set is not exactly 91")
        if args.stage_dir.exists():
            shutil.rmtree(args.stage_dir)
        os.replace(tmp, args.stage_dir)
        tmp = Path()
    finally:
        if tmp and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

    result = {
        "batch": 218,
        "status": "PASS_91_OF_91_BOUND_REPLACEMENTS_MATERIALIZED",
        "binding": {"path": args.binding.as_posix(), "sha256": sha256_file(args.binding)},
        "input_root": args.input_root.resolve().as_posix(),
        "stage_dir": args.stage_dir.as_posix(),
        "asset_count": 91,
        "assets": sorted(rows, key=lambda x: (x["lba"], x["asset"])),
        "safety": {
            "estimated_payload_bytes": 0,
            "disc_bytes_written": 0,
            "gates_preserved": ["SHA256", "EXPECTED_WRITE", "MODE1_2352_EDC_ECC", "91_OF_91_REEXTRACTION"],
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
