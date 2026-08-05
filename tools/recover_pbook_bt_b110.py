#!/usr/bin/env python3
"""Recover the verified Batch110 PBOOK_BT asset from user-owned files.

Scans loose files and ZIP archives for either the exact 87,712-byte asset or a
raw MODE1/2352 Disc 1 image containing it. Only byte-exact source or verified
Batch110 candidate hashes are emitted. No whole disc image is copied.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

RAW_SECTOR = 2352
USER_OFFSET = 16
USER_SIZE = 2048
DISC_SIZE = 659293824
PBOOK_LBA = 15609
PBOOK_SIZE = 87712
SOURCE_SHA = "43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64"
B110_SHA = "4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe"
SOURCE_DISC_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
B110_DISC_SHA = "c6fc9827ee5d8ae17c918a8d7468faa4769601e13329c7485b3df53d5fd17c14"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    while block := stream.read(8 * 1024 * 1024):
        h.update(block)
    return h.hexdigest()


def extract_mode1_asset(stream: BinaryIO, lba: int, size: int) -> bytes:
    remaining = size
    sector = lba
    output = bytearray()
    while remaining:
        stream.seek(sector * RAW_SECTOR + USER_OFFSET)
        take = min(USER_SIZE, remaining)
        block = stream.read(take)
        if len(block) != take:
            raise EOFError(f"short raw image at LBA {sector}")
        output.extend(block)
        remaining -= take
        sector += 1
    return bytes(output)


def classify_asset(data: bytes) -> str | None:
    if len(data) != PBOOK_SIZE:
        return None
    digest = sha256(data)
    if digest == B110_SHA:
        return "B110_VERIFIED_CANDIDATE"
    if digest == SOURCE_SHA:
        return "PRISTINE_SOURCE"
    return None


def emit(data: bytes, kind: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = "PBOOK_BT_B110_VERIFIED.CG" if kind == "B110_VERIFIED_CANDIDATE" else "PBOOK_BT_PRISTINE.CG"
    path = output_dir / name
    path.write_bytes(data)
    expected = B110_SHA if kind == "B110_VERIFIED_CANDIDATE" else SOURCE_SHA
    if sha256(path.read_bytes()) != expected:
        path.unlink(missing_ok=True)
        raise RuntimeError("post-write SHA gate failed")
    return path


def scan_stream(stream: BinaryIO, size: int, label: str, output_dir: Path) -> dict[str, object] | None:
    if size == PBOOK_SIZE:
        stream.seek(0)
        data = stream.read(PBOOK_SIZE)
    elif size == DISC_SIZE:
        data = extract_mode1_asset(stream, PBOOK_LBA, PBOOK_SIZE)
    else:
        return None
    kind = classify_asset(data)
    if not kind:
        return None
    path = emit(data, kind, output_dir)
    return {
        "status": "PASS_EXACT_ASSET_RECOVERED",
        "kind": kind,
        "source": label,
        "output": str(path),
        "asset_sha256": sha256(data),
        "asset_size": len(data),
    }


def scan_file(path: Path, output_dir: Path) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.file_size not in (PBOOK_SIZE, DISC_SIZE):
                        continue
                    with archive.open(info) as member:
                        # ZipExtFile is seekable; extraction remains local and exact.
                        result = scan_stream(member, info.file_size, f"{path}!{info.filename}", output_dir)
                    if result:
                        results.append(result)
        except (zipfile.BadZipFile, OSError, EOFError) as exc:
            results.append({"status": "SCAN_ERROR", "source": str(path), "error": str(exc)})
    elif path.stat().st_size in (PBOOK_SIZE, DISC_SIZE):
        try:
            with path.open("rb") as stream:
                result = scan_stream(stream, path.stat().st_size, str(path), output_dir)
            if result:
                results.append(result)
        except (OSError, EOFError) as exc:
            results.append({"status": "SCAN_ERROR", "source": str(path), "error": str(exc)})
    return results


def scan(root: Path, output_dir: Path) -> dict[str, object]:
    candidates = [p for p in root.rglob("*") if p.is_file()]
    results: list[dict[str, object]] = []
    for path in candidates:
        results.extend(scan_file(path, output_dir))
    exact = [item for item in results if item.get("status") == "PASS_EXACT_ASSET_RECOVERED"]
    report = {
        "status": "PASS_EXACT_RECOVERY" if exact else "BLOCKED_EXACT_BYTES_NOT_FOUND",
        "root": str(root.resolve()),
        "files_scanned": len(candidates),
        "exact_results": exact,
        "scan_errors": [item for item in results if item.get("status") == "SCAN_ERROR"],
        "targets": {"source_sha256": SOURCE_SHA, "b110_sha256": B110_SHA},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "B142_RECOVERY_RESULT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def selftest() -> dict[str, object]:
    pattern = bytes((i * 37 + 11) & 0xFF for i in range(3000))
    raw = bytearray(RAW_SECTOR * 6)
    remaining = pattern
    sector = 2
    while remaining:
        take = min(USER_SIZE, len(remaining))
        start = sector * RAW_SECTOR + USER_OFFSET
        raw[start:start + take] = remaining[:take]
        remaining = remaining[take:]
        sector += 1
    recovered = extract_mode1_asset(io.BytesIO(raw), 2, len(pattern))
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        asset = root / "candidate.CG"
        asset.write_bytes(bytes(PBOOK_SIZE))
        zip_path = root / "sample.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("tiny.bin", raw)
        zip_seek_ok = False
        with zipfile.ZipFile(zip_path) as archive, archive.open("tiny.bin") as member:
            zip_seek_ok = extract_mode1_asset(member, 2, len(pattern)) == pattern
    return {
        "status": "PASS" if recovered == pattern and zip_seek_ok else "FAIL",
        "raw_roundtrip": recovered == pattern,
        "zip_seek_roundtrip": zip_seek_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("scan")
    run.add_argument("root", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("output/B142"))
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else scan(args.root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
