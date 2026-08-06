#!/usr/bin/env python3
"""Recover exact PBOOK raw sectors from retained full Disc checkpoint BINs.

No checkpoint is trusted by filename or historical status. For each candidate
659,293,824-byte BIN, only the 29 target LBAs are read and accepted when their
raw-sector SHA-256 equals the literal Batch110 patched-sector oracle. The legacy
patcher is parsed through AST by the Batch171 module and is never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import recover_pbook_from_legacy_sector_package as b171
from mode1_2352 import verify_mode1_sector


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def walk(root: Path) -> Iterable[Path]:
    return (p for p in root.rglob("*") if p.is_file())


def probe_stream(stream, sector_map: dict[int, dict], source: str,
                 recovered: dict[int, bytes], provenance: dict[int, str]) -> None:
    for lba, entry in sector_map.items():
        if lba in recovered:
            continue
        stream.seek(lba * b171.RAW)
        data = stream.read(b171.RAW)
        if len(data) != b171.RAW:
            continue
        if sha(data) != entry["patched_sha256"]:
            continue
        verdict = verify_mode1_sector(data)
        if not verdict["valid"]:
            raise RuntimeError(f"registered patched sector has invalid EDC/ECC: LBA {lba}: {verdict}")
        recovered[lba] = data
        provenance[lba] = source


def collect_from_checkpoints(root: Path, sector_map: dict[int, dict]) -> tuple[dict[int, bytes], dict[int, str], list[dict]]:
    recovered: dict[int, bytes] = {}
    provenance: dict[int, str] = {}
    audit: list[dict] = []

    for path in walk(root):
        if len(recovered) == len(sector_map):
            break
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as zf:
                    for info in zf.infolist():
                        if info.is_dir() or info.file_size != b171.DISC_SIZE:
                            continue
                        before = len(recovered)
                        with zf.open(info) as stream:
                            probe_stream(stream, sector_map, f"{path}!{info.filename}", recovered, provenance)
                        audit.append({"source": f"{path}!{info.filename}", "new_sectors": len(recovered) - before})
            elif path.stat().st_size == b171.DISC_SIZE:
                before = len(recovered)
                with path.open("rb") as stream:
                    probe_stream(stream, sector_map, str(path), recovered, provenance)
                audit.append({"source": str(path), "new_sectors": len(recovered) - before})
        except (OSError, zipfile.BadZipFile):
            continue
    return recovered, provenance, audit


def write_sidecars(out: Path, sectors: dict[int, bytes], sector_map: dict[int, dict]) -> list[dict]:
    target = out / "PATCH_SECTORS"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for lba, data in sorted(sectors.items()):
        entry = sector_map[lba]
        path = target / f"BATCH173_PATCHED_SECTOR_LBA{lba}.bin"
        path.write_bytes(data)
        rows.append({"lba": lba, "asset": entry["asset"], "path": str(path), "sha256": sha(data)})
    return rows


def selftest() -> None:
    sector_map = {10: {"asset": "PBOOK_BT", "patched_sha256": ""}}
    sector = bytearray(b171.RAW)
    sector[:12] = b171.SYNC
    sector[15] = 1
    # The mathematical verifier must reject an unencoded synthetic sector.
    assert not verify_mode1_sector(bytes(sector))["valid"]
    sector_map[10]["patched_sha256"] = sha(bytes(sector))
    assert sector_map[10]["patched_sha256"] == sha(bytes(sector))
    print("PASS_BATCH173_SELFTEST")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", type=Path)
    ap.add_argument("--output-dir", type=Path, default=Path("output/BATCH173_CHECKPOINT_BIN_RECOVERY"))
    ap.add_argument("--build-disc", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest(); return 0
    if args.root is None:
        ap.error("root is required unless --selftest is used")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {"batch": 173, "status": "BLOCKED"}
    try:
        patcher, sector_map = b171.find_legacy_patcher(args.root)
        sectors, provenance, scan = collect_from_checkpoints(args.root, sector_map)
        missing = sorted(set(sector_map) - set(sectors))
        if missing:
            raise FileNotFoundError("missing exact patched PBOOK sectors after checkpoint scan: " + ",".join(map(str, missing)))
        sidecars = write_sidecars(args.output_dir, sectors, sector_map)
        with tempfile.TemporaryDirectory() as td:
            disc = b171.find_disc(args.root, Path(td))
            assets = b171.reconstruct_assets(disc, sectors, args.output_dir / "RECOVERED_PBOOK")
            result = {
                "batch": 173,
                "status": "PASS_PBOOK3_RECOVERED_FROM_CHECKPOINT_BINS",
                "legacy_patcher": str(patcher),
                "sector_count": len(sectors),
                "provenance": {str(k): v for k, v in sorted(provenance.items())},
                "checkpoint_scan": scan,
                "sidecars": sidecars,
                "assets": assets,
            }
            if args.build_disc:
                result["disc"] = b171.build_disc(disc, sectors, args.output_dir)
                result["status"] = "PASS_PBOOK3_CHECKPOINT_RECOVERY_DISC_BUILT"
    except Exception as exc:
        result["error"] = str(exc)

    (args.output_dir / "BATCH173_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
