#!/usr/bin/env python3
"""Independently audit MODE1/2352 EDC/ECC in ST2 sparse patch packages."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

import recover_assets_from_sparse_packages as sparse
from recover_integrate_production_assets import make_sector, rebuild_sector, valid_sector


def audit(source_path: Path, package_path: Path) -> dict:
    reader = sparse.DirectoryReader(package_path) if package_path.is_dir() else sparse.ZipReader(package_path)
    close = getattr(reader, "close", None)
    try:
        metadata = sparse.find_package_metadata(reader)
        if not metadata:
            raise ValueError("no APPLY contract")
        source_size = source_path.stat().st_size
        source_sha = sparse.sha_file(source_path)
        failures: list[str] = []
        for meta in sorted(metadata, key=lambda item: len(item.assets), reverse=True):
            if source_size != meta.disc_size or source_sha != meta.source_sha256:
                continue
            try:
                delta_dir, manifest = sparse.find_delta_set(reader, meta)
                with source_path.open("rb") as source:
                    for entry in manifest:
                        lba = int(entry["lba"])
                        original = sparse.read_source_sector(source, lba, meta.raw)
                        if not valid_sector(original):
                            raise ValueError(f"original LBA {lba} EDC/ECC mismatch")
                    patched = sparse.apply_delta_set(reader, delta_dir, manifest, source, meta.raw)
                bad = [lba for lba, sector in patched.items() if not valid_sector(sector)]
                if bad:
                    raise ValueError(f"patched EDC/ECC mismatch: {bad[:8]}")
                return {
                    "status": "PASS_SPARSE_PACKAGE_MODE1_EDC_ECC",
                    "package": str(package_path),
                    "package_sha256": sparse.sha_file(package_path) if package_path.is_file() else None,
                    "apply_contract": meta.script_name,
                    "source_disc_sha256": source_sha,
                    "changed_raw_sectors": len(patched),
                    "original_mode1_edc_ecc": f"PASS_{len(patched)}_OF_{len(patched)}",
                    "patched_mode1_edc_ecc": f"PASS_{len(patched)}_OF_{len(patched)}",
                }
            except Exception as exc:
                failures.append(f"{meta.script_name}: {exc}")
        raise ValueError("; ".join(failures) or "no source-compatible contract")
    finally:
        if close:
            close()


def selftest() -> dict:
    raw = 2352
    sectors = [make_sector(lba, bytes(((lba * 17 + i) & 255) for i in range(2048))) for lba in range(5)]
    source_bytes = b"".join(sectors)
    lba = 2
    original = sectors[lba]
    changed = bytearray(original)
    changed[20:24] = b"TEST"
    patched = rebuild_sector(bytes(changed))
    candidate = bytearray(source_bytes)
    candidate[lba * raw:(lba + 1) * raw] = patched
    spans = []
    cursor = 0
    while cursor < raw:
        if original[cursor] == patched[cursor]:
            cursor += 1
            continue
        start = cursor
        while cursor < raw and original[cursor] != patched[cursor]:
            cursor += 1
        spans.append({"offset": start, "old_sha256": sparse.sha_bytes(original[start:cursor]), "data_hex": patched[start:cursor].hex()})
    manifest = [{"lba": lba, "original_sector_sha256": sparse.sha_bytes(original), "patched_sector_sha256": sparse.sha_bytes(patched)}]
    delta = {**manifest[0], "spans": spans}
    asset = patched[16:80]
    script = f"RAW={raw}\nDISC_SIZE={len(source_bytes)}\nDISC_SHA='{sparse.sha_bytes(source_bytes)}'\nOUTPUT_SHA='{sparse.sha_bytes(candidate)}'\nASSETS=[('A',{lba},{len(asset)},'{sparse.sha_bytes(asset)}')]\n"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "source.bin"
        package = root / "package.zip"
        source.write_bytes(source_bytes)
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("P/APPLY_TEST.py", script)
            archive.writestr("P/DELTA/MANIFEST.json", json.dumps(manifest))
            archive.writestr(f"P/DELTA/LBA{lba}.json", json.dumps(delta))
        result = audit(source, package)
    return {"status": "PASS" if result["status"].startswith("PASS") else "FAIL", "mode1_edc_ecc": result["patched_mode1_edc_ecc"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("source_bin", type=Path)
    verify.add_argument("package", type=Path)
    verify.add_argument("--result", type=Path)
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else audit(args.source_bin, args.package)
    if getattr(args, "result", None):
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
