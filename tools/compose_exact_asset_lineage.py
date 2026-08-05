#!/usr/bin/env python3
"""Compose cumulative exact-asset recovery manifests from a trusted base and ordered deltas.

No binary bytes are generated. Every asset must already have an exact whole-file
SHA-256, LBA and size. Duplicate names/LBAs and lineage discontinuities fail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def validate_asset(asset: dict) -> dict:
    required = {"name", "filename", "source_batch", "lba", "size", "target_sha256"}
    missing = required - set(asset)
    if missing:
        raise ValueError(f"asset missing fields {sorted(missing)}: {asset}")
    out = dict(asset)
    if not isinstance(out["name"], str) or not out["name"]:
        raise ValueError("invalid asset name")
    if not isinstance(out["filename"], str) or not out["filename"]:
        raise ValueError(f"invalid filename: {out['name']}")
    for field in ("source_batch", "lba", "size"):
        if not isinstance(out[field], int) or out[field] < 0:
            raise ValueError(f"invalid {field}: {out['name']}")
    if out["size"] == 0 or not SHA_RE.fullmatch(out["target_sha256"]):
        raise ValueError(f"invalid size/SHA: {out['name']}")
    return out


def validate_disc(disc: dict) -> dict:
    required = {"size", "sha256", "raw_sector_size", "user_data_offset", "user_data_size"}
    if required - set(disc):
        raise ValueError("source_disc contract incomplete")
    if disc["size"] <= 0 or disc["raw_sector_size"] <= 0 or disc["user_data_size"] <= 0:
        raise ValueError("invalid source_disc dimensions")
    if not SHA_RE.fullmatch(disc["sha256"]):
        raise ValueError("invalid source_disc SHA-256")
    return dict(disc)


def compose(base_path: Path, delta_paths: list[Path]) -> dict:
    base = load_json(base_path)
    if base.get("schema") != "st2-exact-asset-recovery-v1":
        raise ValueError("unsupported base schema")
    disc = validate_disc(base["source_disc"])
    assets = [validate_asset(a) for a in base["assets"]]
    batch = int(base["batch"])
    names = {a["name"] for a in assets}
    lbas = {a["lba"] for a in assets}
    if len(names) != len(assets) or len(lbas) != len(assets):
        raise ValueError("base duplicate asset name or LBA")

    lineage = [{"batch": batch, "asset_count": len(assets), "source": str(base_path)}]
    history = dict(base.get("historical_verification", {}))

    for path in delta_paths:
        delta = load_json(path)
        if delta.get("schema") != "st2-exact-asset-lineage-delta-v1":
            raise ValueError(f"unsupported delta schema: {path}")
        if delta.get("expected_base_batch") != batch:
            raise ValueError(f"batch discontinuity at {path}: expected {batch}")
        if delta.get("expected_base_assets") != len(assets):
            raise ValueError(f"asset-count discontinuity at {path}")
        if delta.get("source_disc_sha256") != disc["sha256"]:
            raise ValueError(f"source Disc mismatch at {path}")
        additions = [validate_asset(a) for a in delta.get("assets", [])]
        if len(additions) != delta.get("added_asset_count"):
            raise ValueError(f"added asset count mismatch at {path}")
        for asset in additions:
            if asset["name"] in names:
                raise ValueError(f"duplicate asset name: {asset['name']}")
            if asset["lba"] in lbas:
                raise ValueError(f"duplicate starting LBA: {asset['lba']}")
            names.add(asset["name"]); lbas.add(asset["lba"]); assets.append(asset)
        batch = int(delta["batch"])
        if len(assets) != delta.get("cumulative_asset_count"):
            raise ValueError(f"cumulative asset count mismatch at {path}")
        history = dict(delta.get("cumulative_verification", {}))
        if history.get("asset_count") != len(assets):
            raise ValueError(f"historical verification asset count mismatch at {path}")
        lineage.append({"batch": batch, "asset_count": len(assets), "source": str(path)})

    result = {
        "schema": "st2-exact-asset-recovery-v1",
        "batch": batch,
        "purpose": f"Recover the exact cumulative Batch {batch} Korean Disc 1 battle/static assets from retained loose files, ZIP archives, or raw MODE1/2352 checkpoint BINs.",
        "source_disc": disc,
        "historical_verification": history,
        "lineage": lineage,
        "assets": assets,
    }
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    result["manifest_content_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result


def selftest() -> dict:
    disc = {"size": 1000, "sha256": "0" * 64, "raw_sector_size": 2352,
            "user_data_offset": 16, "user_data_size": 2048}
    base = {"schema": "st2-exact-asset-recovery-v1", "batch": 1, "source_disc": disc,
            "historical_verification": {"asset_count": 1}, "assets": [
                {"name": "A", "filename": "A.MES", "source_batch": 1,
                 "lba": 10, "size": 7, "target_sha256": "1" * 64}]}
    d2 = {"schema": "st2-exact-asset-lineage-delta-v1", "batch": 2,
          "expected_base_batch": 1, "expected_base_assets": 1,
          "source_disc_sha256": "0" * 64, "added_asset_count": 1,
          "cumulative_asset_count": 2, "cumulative_verification": {"asset_count": 2},
          "assets": [{"name": "B", "filename": "B.MES", "source_batch": 2,
                      "lba": 20, "size": 8, "target_sha256": "2" * 64}]}
    d3 = {"schema": "st2-exact-asset-lineage-delta-v1", "batch": 3,
          "expected_base_batch": 2, "expected_base_assets": 2,
          "source_disc_sha256": "0" * 64, "added_asset_count": 1,
          "cumulative_asset_count": 3, "cumulative_verification": {"asset_count": 3},
          "assets": [{"name": "C", "filename": "C.CG", "source_batch": 3,
                      "lba": 30, "size": 9, "target_sha256": "3" * 64}]}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        paths = []
        for name, obj in (("base.json", base), ("d2.json", d2), ("d3.json", d3)):
            p = root / name; p.write_text(json.dumps(obj), encoding="utf-8"); paths.append(p)
        result = compose(paths[0], paths[1:])
        duplicate_blocked = False
        bad = dict(d3); bad["assets"] = [dict(d3["assets"][0], name="B")]
        bp = root / "bad.json"; bp.write_text(json.dumps(bad), encoding="utf-8")
        try:
            compose(paths[0], [paths[1], bp])
        except ValueError:
            duplicate_blocked = True
    ok = result["batch"] == 3 and len(result["assets"]) == 3 and duplicate_blocked
    return {"status": "PASS" if ok else "FAIL", "assets": len(result["assets"]),
            "duplicate_blocked": duplicate_blocked}


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose")
    c.add_argument("base", type=Path)
    c.add_argument("deltas", nargs="+", type=Path)
    c.add_argument("--output", required=True, type=Path)
    sub.add_parser("selftest")
    args = p.parse_args()
    if args.cmd == "selftest":
        result = selftest()
    else:
        result = compose(args.base, args.deltas)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {"status": "PASS", "batch": result["batch"],
                  "asset_count": len(result["assets"]), "output": str(args.output),
                  "manifest_content_sha256": result["manifest_content_sha256"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
