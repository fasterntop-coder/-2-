#!/usr/bin/env python3
"""Independently verify and seal the 91-asset materialized CD1 staging tree.

The stage must contain exactly the files declared by Batch218, with no extras,
symlinks, path aliases, size drift, or SHA-256 drift. The Batch218 manifest is
also bound back to the exact 91-asset write plan. No Disc image is opened.
"""
from __future__ import annotations

import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_obj(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def plan_records(plan: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("writes", "assets", "write_plan"):
        value = plan.get(key)
        if isinstance(value, list):
            return value
    raise ValueError("write plan record list not found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialized", type=Path, default=Path("output/BATCH218_MATERIALIZED_REPLACEMENTS.json"))
    ap.add_argument("--write-plan", type=Path, default=Path("output/CD1_91_ASSET_WRITE_PLAN.json"))
    ap.add_argument("--stage-dir", type=Path, default=Path("output/CD1_BOUND_REPLACEMENTS"))
    ap.add_argument("--output", type=Path, default=Path("output/BATCH219_MATERIALIZED_STAGE_SEAL.json"))
    args = ap.parse_args()

    mat, plan = load_obj(args.materialized), load_obj(args.write_plan)
    if mat.get("status") != "PASS_91_OF_91_BOUND_REPLACEMENTS_MATERIALIZED" or mat.get("asset_count") != 91:
        raise ValueError("Batch218 manifest is not a complete 91-asset PASS")
    assets = mat.get("assets")
    if not isinstance(assets, list) or len(assets) != 91:
        raise ValueError("Batch218 assets must contain exactly 91 records")

    expected: dict[str, dict[str, Any]] = {}
    for rec in plan_records(plan):
        if not isinstance(rec, dict):
            raise ValueError("non-object write-plan record")
        name = rec.get("asset") or rec.get("name")
        sha = rec.get("replacement_sha256") or rec.get("sha256")
        size = rec.get("size")
        if not isinstance(name, str) or name in expected:
            raise ValueError(f"invalid or duplicate plan asset: {name!r}")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"invalid plan size: {name}")
        if not isinstance(sha, str) or not HEX64.fullmatch(sha):
            raise ValueError(f"invalid plan SHA-256: {name}")
        expected[name] = {"size": size, "sha256": sha, "lba": rec.get("lba"), "scope": rec.get("scope")}
    if len(expected) != 91:
        raise ValueError(f"write plan must contain exactly 91 unique assets, got {len(expected)}")

    stage = args.stage_dir.resolve(strict=True)
    if not stage.is_dir():
        raise ValueError("stage path is not a directory")
    actual_files = []
    for p in stage.iterdir():
        if p.is_symlink() or not p.is_file():
            raise ValueError(f"stage contains symlink or non-file entry: {p.name}")
        actual_files.append(p.name)

    declared_files: set[str] = set()
    rows = []
    seen_assets: set[str] = set()
    for rec in assets:
        if not isinstance(rec, dict):
            raise ValueError("non-object Batch218 asset record")
        asset, filename = rec.get("asset"), rec.get("staged_file")
        if not isinstance(asset, str) or asset in seen_assets or asset not in expected:
            raise ValueError(f"invalid, duplicate, or unknown asset: {asset!r}")
        if not isinstance(filename, str) or Path(filename).name != filename or filename in declared_files:
            raise ValueError(f"unsafe or duplicate staged filename: {filename!r}")
        exp = expected[asset]
        if rec.get("size") != exp["size"] or rec.get("sha256") != exp["sha256"]:
            raise ValueError(f"Batch218/plan mismatch: {asset}")
        p = stage / filename
        if p.is_symlink() or not p.is_file():
            raise ValueError(f"declared staged file missing or unsafe: {filename}")
        actual_size, actual_sha = p.stat().st_size, sha256_file(p)
        if actual_size != exp["size"] or actual_sha != exp["sha256"]:
            raise ValueError(f"staged payload drift: {asset}")
        seen_assets.add(asset); declared_files.add(filename)
        rows.append({"asset": asset, "staged_file": filename, "lba": exp["lba"], "scope": exp["scope"], "size": actual_size, "sha256": actual_sha, "status": "PASS"})

    if seen_assets != set(expected):
        raise ValueError("Batch218 asset set is not bijective with the 91-asset write plan")
    if set(actual_files) != declared_files:
        raise ValueError(f"stage contains missing or extra files: declared={len(declared_files)} actual={len(actual_files)}")

    rows.sort(key=lambda x: ((x["lba"] if isinstance(x["lba"], int) else -1), x["asset"]))
    canonical = "".join(f'{r["asset"]}\0{r["staged_file"]}\0{r["size"]}\0{r["sha256"]}\n' for r in rows).encode()
    result = {
        "batch": 219,
        "status": "PASS_91_OF_91_MATERIALIZED_STAGE_SEALED",
        "asset_count": 91,
        "materialized_manifest": {"path": args.materialized.as_posix(), "sha256": sha256_file(args.materialized)},
        "write_plan": {"path": args.write_plan.as_posix(), "sha256": sha256_file(args.write_plan)},
        "stage_dir": args.stage_dir.as_posix(),
        "stage_tree_sha256": hashlib.sha256(canonical).hexdigest(),
        "assets": rows,
        "safety": {"estimated_payload_bytes": 0, "disc_bytes_written": 0, "gates_preserved": ["SHA256", "EXPECTED_WRITE", "MODE1_2352_EDC_ECC", "91_OF_91_REEXTRACTION"]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"], result["stage_tree_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
