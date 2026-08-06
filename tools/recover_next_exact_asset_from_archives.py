#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

RAW_SECTOR = 2352
USER_OFF = 16
USER_SIZE = 2048


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_assignment(script: Path, name: str):
    tree = ast.parse(script.read_text(encoding="utf-8", errors="strict"), filename=str(script))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return ast.literal_eval(node.value)
    raise ValueError(f"assignment not found: {name}")


def iter_loose(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and not p.is_symlink():
            yield p


def collect_sector_matches(roots: list[Path], wanted: dict[str, int]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for root in roots:
        for p in iter_loose(root):
            try:
                if p.suffix.lower() == ".zip":
                    with zipfile.ZipFile(p) as zf:
                        for zi in zf.infolist():
                            if zi.is_dir() or zi.file_size != RAW_SECTOR:
                                continue
                            b = zf.read(zi)
                            h = sha256(b)
                            if h in wanted and h not in found:
                                found[h] = {"kind": "zip", "path": str(p), "member": zi.filename, "lba": wanted[h], "bytes": b}
                elif p.stat().st_size == RAW_SECTOR:
                    b = p.read_bytes()
                    h = sha256(b)
                    if h in wanted and h not in found:
                        found[h] = {"kind": "loose", "path": str(p), "lba": wanted[h], "bytes": b}
                elif p.suffix.lower() in {".bin", ".img"} and p.stat().st_size % RAW_SECTOR == 0:
                    with p.open("rb") as f:
                        for h, lba in wanted.items():
                            if h in found:
                                continue
                            f.seek(lba * RAW_SECTOR)
                            b = f.read(RAW_SECTOR)
                            if len(b) == RAW_SECTOR and sha256(b) == h:
                                found[h] = {"kind": "disc", "path": str(p), "lba": lba, "bytes": b}
            except (OSError, zipfile.BadZipFile):
                continue
    return found


def rebuild_asset(pristine_disc: Path, lba: int, size: int, sector_rows: list[tuple[int, bytes]]) -> bytes:
    first = lba
    last = (lba * USER_SIZE + size - 1) // USER_SIZE
    chunks = []
    replacement = {x: b for x, b in sector_rows}
    with pristine_disc.open("rb") as f:
        for sector_lba in range(first, last + 1):
            if sector_lba in replacement:
                raw = replacement[sector_lba]
            else:
                f.seek(sector_lba * RAW_SECTOR)
                raw = f.read(RAW_SECTOR)
            if len(raw) != RAW_SECTOR:
                raise ValueError(f"short sector at LBA {sector_lba}")
            chunks.append(raw[USER_OFF:USER_OFF + USER_SIZE])
    return b"".join(chunks)[:size]


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover one exact CD1 asset using archived raw-sector SHA oracles.")
    ap.add_argument("--apply-script", required=True, type=Path)
    ap.add_argument("--asset-manifest", required=True, type=Path)
    ap.add_argument("--asset", default="SYS22")
    ap.add_argument("--pristine-disc", required=True, type=Path)
    ap.add_argument("--search-root", action="append", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    ns = ap.parse_args()

    sectors = load_assignment(ns.apply_script, "SECTORS")
    manifest = json.loads(ns.asset_manifest.read_text(encoding="utf-8"))
    bank = next((x for x in manifest["banks"] if x["bank"] == ns.asset), None)
    if bank is None:
        raise SystemExit(f"asset missing from manifest: {ns.asset}")

    rows = []
    wanted = {}
    for k, v in sectors.items():
        if v.get("asset") == ns.asset:
            lba = int(k)
            h = v["patched_sha256"].lower()
            wanted[h] = lba
            rows.append((lba, h, v["original_sha256"].lower()))
    rows.sort()
    if not rows:
        raise SystemExit(f"no sector oracle for {ns.asset}")

    found = collect_sector_matches(ns.search_root, wanted)
    missing = [{"lba": lba, "patched_sha256": h} for lba, h, _ in rows if h not in found]
    result = {
        "status": "BLOCKED_MISSING_EXACT_SECTORS" if missing else "PASS_EXACT_ASSET_RECOVERED",
        "asset": ns.asset,
        "lba": bank["lba"],
        "size": bank["size"],
        "target_sha256": bank["candidate_sha256"],
        "sector_count": len(rows),
        "found_sector_count": len(rows) - len(missing),
        "missing": missing,
        "sources": [{k: v for k, v in rec.items() if k != "bytes"} for rec in found.values()],
        "estimated_bytes": 0,
    }

    if not missing:
        rebuilt = rebuild_asset(ns.pristine_disc, bank["lba"], bank["size"], [(wanted[h], rec["bytes"]) for h, rec in found.items()])
        got = sha256(rebuilt)
        result["recovered_sha256"] = got
        if got != bank["candidate_sha256"].lower():
            result["status"] = "FAIL_REBUILT_ASSET_SHA256"
            ns.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 2
        ns.output.parent.mkdir(parents=True, exist_ok=True)
        ns.output.write_bytes(rebuilt)
        if sha256(ns.output.read_bytes()) != got:
            raise SystemExit("post-write SHA mismatch")

    ns.report.parent.mkdir(parents=True, exist_ok=True)
    ns.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "PASS_EXACT_ASSET_RECOVERED" else 3


if __name__ == "__main__":
    sys.exit(main())
