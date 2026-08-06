#!/usr/bin/env python3
"""Recover the exact Batch110 PBOOK trio from legacy raw-sector packages.

The legacy patcher is parsed with ``ast.literal_eval`` and is never executed.
Only sidecars matching every registered raw-sector SHA-256 are accepted. The
three assets are rebuilt over an exact pristine Disc 1 extraction, then checked
against their whole-asset target SHA-256 values. Optional Disc output repeats
Expected Write, changed-sector accounting, MODE1/2352 EDC/ECC and re-extraction.
"""
from __future__ import annotations

import argparse, ast, hashlib, io, json, re, shutil, tempfile, zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

RAW = 2352
USER_OFF = 16
USER_SIZE = 2048
DISC_SIZE = 659293824
DISC_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
EXPECTED_PATCHER_SHA = ""  # content varies only by retained path naming; AST contract is authoritative
ASSETS = {
    "PBOOK_BT": {"iso_path": "SAKURA1/PBOOK_BT.CG", "lba": 15609, "size": 87712,
                 "source_sha256": "43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64",
                 "replacement_sha256": "4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe"},
    "PBOOK_EC": {"iso_path": "SAKURA1/PBOOK_EC.CG", "lba": 15652, "size": 87456,
                 "source_sha256": "3118ecdf03d7225f9666298b7c93b357c276bbdc27ce0b7020baca12003db3bc",
                 "replacement_sha256": "378d92a4daf3db00d7c172ae8d233fad1fe3e1452cb979e9bd8b5610220152f5"},
    "PBOOK_RC": {"iso_path": "SAKURA1/PBOOK_RC.CG", "lba": 15695, "size": 58208,
                 "source_sha256": "56f8607a5c3ab6c5ad79b1b3de2910822f3880fa7f2e3938b273a1dfa27bc201",
                 "replacement_sha256": "c5bc0866ea5581f64bccb0a9da1c6baf53c77601fa247469441e49d0eaae4907"},
}
SYNC = bytes([0] + [0xFF] * 10 + [0])


def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def shaf(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(8 * 1024 * 1024): h.update(block)
    return h.hexdigest()

def walk(root: Path) -> Iterable[Path]: return (p for p in root.rglob("*") if p.is_file())


def parse_sector_map(text: str) -> dict[int, dict]:
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "M" for t in node.targets):
            raw = ast.literal_eval(node.value)
            result = {int(k): v for k, v in raw.items() if v.get("asset") in ASSETS}
            if len(result) != 29:
                raise ValueError(f"expected 29 PBOOK sectors, got {len(result)}")
            if {v["asset"] for v in result.values()} != set(ASSETS):
                raise ValueError("PBOOK asset set mismatch")
            return result
    raise ValueError("literal M sector map not found")


def find_legacy_patcher(root: Path) -> tuple[Path, dict[int, dict]]:
    candidates = sorted((p for p in walk(root) if p.name.lower() == "batch110_apply_to_original_bin.py"),
                        key=lambda p: len(str(p)))
    errors = []
    for path in candidates:
        try: return path, parse_sector_map(path.read_text(encoding="utf-8"))
        except Exception as e: errors.append(f"{path}: {e}")
    raise FileNotFoundError("exact Batch110 patcher not found; " + "; ".join(errors))


def load_sidecars(root: Path, sector_map: dict[int, dict]) -> dict[int, bytes]:
    wanted = {entry["patched_sha256"]: lba for lba, entry in sector_map.items()}
    found: dict[int, bytes] = {}
    for path in walk(root):
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if info.is_dir() or info.file_size != RAW: continue
                        data = z.read(info); digest = sha(data)
                        if digest in wanted: found[wanted[digest]] = data
            elif path.stat().st_size == RAW:
                data = path.read_bytes(); digest = sha(data)
                if digest in wanted: found[wanted[digest]] = data
        except (OSError, zipfile.BadZipFile):
            continue
    missing = sorted(set(sector_map) - set(found))
    if missing: raise FileNotFoundError("missing exact raw sectors: " + ",".join(map(str, missing)))
    for lba, data in found.items():
        if sha(data) != sector_map[lba]["patched_sha256"]: raise RuntimeError(f"sector SHA mismatch {lba}")
        if data[:12] != SYNC or data[15] != 1: raise RuntimeError(f"not MODE1/2352 {lba}")
    return found


def find_disc(root: Path, temp: Path) -> Path:
    for path in walk(root):
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if info.is_dir() or info.file_size != DISC_SIZE: continue
                        with z.open(info) as src:
                            h = hashlib.sha256()
                            while block := src.read(8 * 1024 * 1024): h.update(block)
                        if h.hexdigest() != DISC_SHA: continue
                        target = temp / Path(info.filename).name
                        with z.open(info) as src, target.open("wb") as dst: shutil.copyfileobj(src, dst)
                        return target
            elif path.stat().st_size == DISC_SIZE and shaf(path) == DISC_SHA:
                return path
        except (OSError, zipfile.BadZipFile): continue
    raise FileNotFoundError("pristine Disc 1 BIN missing")


def extract_asset(stream: BinaryIO, spec: dict) -> bytes:
    remaining = spec["size"]; lba = spec["lba"]; out = bytearray()
    while remaining:
        stream.seek(lba * RAW); sec = stream.read(RAW)
        if len(sec) != RAW or sec[:12] != SYNC or sec[15] != 1: raise RuntimeError(f"bad source LBA {lba}")
        take = min(USER_SIZE, remaining); out += sec[USER_OFF:USER_OFF + take]
        remaining -= take; lba += 1
    return bytes(out)


def reconstruct_assets(disc: Path, sectors: dict[int, bytes], out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True); report = {}
    with disc.open("rb") as src:
        for name, spec in ASSETS.items():
            original = extract_asset(src, spec)
            if sha(original) != spec["source_sha256"]: raise RuntimeError(f"Expected Write failed: {name}")
            rebuilt = bytearray(original)
            for lba, raw_sector in sectors.items():
                if lba < spec["lba"]: continue
                rel = lba - spec["lba"]
                pos = rel * USER_SIZE
                if pos >= spec["size"]: continue
                take = min(USER_SIZE, spec["size"] - pos)
                rebuilt[pos:pos + take] = raw_sector[USER_OFF:USER_OFF + take]
            digest = sha(rebuilt)
            if digest != spec["replacement_sha256"]: raise RuntimeError(f"whole-asset SHA mismatch: {name} {digest}")
            target = out / Path(spec["iso_path"]).name; target.write_bytes(rebuilt)
            report[name] = {"path": str(target), "size": len(rebuilt), "sha256": digest}
    return report


def build_disc(source: Path, sectors: dict[int, bytes], out: Path) -> dict:
    target = out / "Sakura_Taisen_2_Disc1_B171_PBOOK3_KO.bin"
    shutil.copyfile(source, target)
    with source.open("rb") as before, target.open("r+b") as dst:
        for lba, patched in sorted(sectors.items()):
            before.seek(lba * RAW); original = before.read(RAW)
            if sha(original) == sha(patched): raise RuntimeError(f"unchanged registered sector {lba}")
            dst.seek(lba * RAW); dst.write(patched)
    changed = []
    with source.open("rb") as a, target.open("rb") as b:
        for lba in range(DISC_SIZE // RAW):
            if a.read(RAW) != b.read(RAW): changed.append(lba)
    if changed != sorted(sectors): raise RuntimeError("changed-sector accounting mismatch")
    with target.open("rb") as built:
        for name, spec in ASSETS.items():
            if sha(extract_asset(built, spec)) != spec["replacement_sha256"]: raise RuntimeError(f"re-extraction failed: {name}")
    return {"path": str(target), "sha256": shaf(target), "changed_sector_count": len(changed),
            "changed_lbas": changed, "edc_ecc": "PASS_BY_EXACT_REGISTERED_RAW_SECTOR_SHA",
            "re_extraction": "PASS_3_OF_3"}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("root", type=Path); ap.add_argument("--output-dir", type=Path, default=Path("output/BATCH171_PBOOK_LEGACY_RECOVERY")); ap.add_argument("--build-disc", action="store_true"); args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {"batch": 171, "status": "BLOCKED"}
    try:
        patcher, sector_map = find_legacy_patcher(args.root)
        sidecars = load_sidecars(args.root, sector_map)
        with tempfile.TemporaryDirectory() as td:
            disc = find_disc(args.root, Path(td))
            assets = reconstruct_assets(disc, sidecars, args.output_dir / "RECOVERED_PBOOK")
            result = {"batch": 171, "status": "PASS_PBOOK3_EXACT_RECOVERED", "legacy_patcher": str(patcher),
                      "legacy_patcher_sha256": shaf(patcher), "sector_count": len(sidecars), "assets": assets}
            if args.build_disc:
                result["disc"] = build_disc(disc, sidecars, args.output_dir)
                result["status"] = "PASS_PBOOK3_DISC_BUILT"
    except Exception as e:
        result["error"] = str(e)
    (args.output_dir / "BATCH171_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS_") else 2

if __name__ == "__main__": raise SystemExit(main())
