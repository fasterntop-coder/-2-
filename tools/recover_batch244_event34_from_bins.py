#!/usr/bin/env python3
"""Recover Batch244 compiled EVENT MES payloads from historical BIN/ZIP candidates.

This tool does not guess bytes. It extracts the 34 known EVENT assets at their canonical
Disc 1 LBAs, hashes each whole asset, and only accepts payloads whose SHA-256 exactly
matches CD1_BATCH244_EVENT34_PROMOTION.json. Multiple old cumulative BINs and ZIPs may
be scanned in one invocation; the first exact match for each asset is materialized into
an output directory suitable for integrate_batch244_event34.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

SECTOR = 2352
USER_OFF = 16
USER_SIZE = 2048


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_raw_mode1_asset(f, lba: int, size: int) -> bytes:
    out = bytearray()
    remain = size
    cur = lba
    while remain:
        f.seek(cur * SECTOR + USER_OFF)
        take = min(USER_SIZE, remain)
        chunk = f.read(take)
        if len(chunk) != take:
            raise EOFError(f"short read at LBA {cur}: {len(chunk)} != {take}")
        out.extend(chunk)
        remain -= take
        cur += 1
    return bytes(out)


def load_manifest(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("asset_count") != 34 or len(obj.get("replacement_files", [])) != 34:
        raise ValueError("manifest is not the 34-asset Batch244 promotion manifest")
    return obj


def scan_bin(bin_path: Path, assets: list[dict], recovered: dict[str, dict], out_dir: Path) -> None:
    size = bin_path.stat().st_size
    if size < 659_000_000:
        return
    with bin_path.open("rb") as f:
        for a in assets:
            iso = a["iso_path"]
            if iso in recovered:
                continue
            try:
                data = read_raw_mode1_asset(f, int(a["lba"]), int(a["size"]))
            except EOFError:
                continue
            got = sha256(data)
            if got != a["replacement_sha256"]:
                continue
            name = Path(iso).name
            dst = out_dir / name
            dst.write_bytes(data)
            recovered[iso] = {
                "source_container": str(bin_path),
                "output": str(dst),
                "size": len(data),
                "sha256": got,
                "status": "EXACT_REPLACEMENT_SHA256_MATCH",
            }
            print(f"RECOVERED {iso} <- {bin_path.name}")


def iter_candidate_bins(inputs: list[Path]):
    for p in inputs:
        if p.is_dir():
            for q in sorted(p.rglob("*")):
                if q.is_file() and q.suffix.lower() == ".bin":
                    yield (q, None)
            continue
        if p.suffix.lower() == ".bin":
            yield (p, None)
            continue
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p, "r") as zf:
                members = [i for i in zf.infolist() if not i.is_dir() and i.filename.lower().endswith(".bin")]
                for info in members:
                    tmp = tempfile.NamedTemporaryFile(prefix="st2_b244_", suffix=".bin", delete=False)
                    tmp_path = Path(tmp.name)
                    tmp.close()
                    try:
                        with zf.open(info, "r") as src, tmp_path.open("wb") as dst:
                            shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
                        yield (tmp_path, f"{p}!{info.filename}")
                    finally:
                        try:
                            tmp_path.unlink()
                        except FileNotFoundError:
                            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path, help="historical BIN/ZIP files or directories")
    ap.add_argument("--manifest", type=Path, default=Path("manifests/CD1_BATCH244_EVENT34_PROMOTION.json"))
    ap.add_argument("--out", type=Path, default=Path("BATCH244_RECOVERED_EVENT34"))
    ap.add_argument("--report", type=Path, default=Path("BATCH244_RECOVERY_REPORT.json"))
    ns = ap.parse_args()

    manifest = load_manifest(ns.manifest)
    assets = manifest["replacement_files"]
    ns.out.mkdir(parents=True, exist_ok=True)
    recovered: dict[str, dict] = {}
    scanned: list[str] = []

    for physical, display in iter_candidate_bins(ns.inputs):
        label = display or str(physical)
        scanned.append(label)
        before = set(recovered)
        scan_bin(physical, assets, recovered, ns.out)
        if display:
            for iso in set(recovered) - before:
                recovered[iso]["source_container"] = display
        if len(recovered) == 34:
            break

    missing = [a["iso_path"] for a in assets if a["iso_path"] not in recovered]
    report = {
        "format": "ST2-CD1-BATCH244-BULK-RECOVERY-v1",
        "manifest": str(ns.manifest),
        "target_assets": 34,
        "recovered_assets": len(recovered),
        "missing_assets": len(missing),
        "all_exact_matches": len(recovered) == 34,
        "guessed_payload_bytes": False,
        "scanned_containers": scanned,
        "recovered": recovered,
        "missing": missing,
        "next_step": "python tools/integrate_batch244_event34.py ..." if len(recovered) == 34 else "scan additional historical cumulative BIN/ZIP candidates",
    }
    ns.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RESULT recovered={len(recovered)}/34 missing={len(missing)} report={ns.report}")
    return 0 if len(recovered) == 34 else 2


if __name__ == "__main__":
    raise SystemExit(main())
