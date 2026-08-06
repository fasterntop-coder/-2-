#!/usr/bin/env python3
"""Recover exact ST2 assets from executable sparse raw-sector patch packages.

Package Python is NEVER executed. Literal contracts are parsed with AST. Every
raw-sector delta is accepted only after source-sector SHA, per-span Expected
Write SHA, patched-sector SHA, complete candidate Disc SHA, and whole-asset
re-extraction SHA all match.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Mapping

RAW_DEFAULT = 2352
USER_OFFSET = 16
USER_SIZE = 2048
CHUNK = 8 * 1024 * 1024
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def literal_assignments(source: str) -> dict[str, object]:
    tree = ast.parse(source)
    out: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if node.value is None:
            continue
        try:
            literal = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                out[target.id] = literal
    return out


def normalize_assets(value: object) -> list[dict]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("ASSETS is not a list")
    assets: list[dict] = []
    names: set[str] = set()
    lbas: set[int] = set()
    for row in value:
        if isinstance(row, dict):
            name = str(row.get("name") or row.get("asset"))
            lba = int(row["lba"])
            size = int(row["size"])
            target = str(row.get("target_sha256") or row.get("sha256") or row.get("target_sha"))
        elif isinstance(row, (list, tuple)) and len(row) >= 4:
            name, lba, size, target = str(row[0]), int(row[1]), int(row[2]), str(row[3])
        else:
            raise ValueError(f"invalid asset row: {row!r}")
        target = target.lower()
        if not name or lba < 0 or size <= 0 or not HEX64.fullmatch(target):
            raise ValueError(f"invalid asset metadata: {row!r}")
        if name in names or lba in lbas:
            raise ValueError(f"duplicate asset name/LBA: {name} {lba}")
        names.add(name)
        lbas.add(lba)
        suffix = ".CG" if name.startswith("PBOOK_") else ".MES"
        assets.append({"name": name, "filename": name + suffix, "lba": lba, "size": size, "target_sha256": target})
    return assets


@dataclass(frozen=True)
class PackageMetadata:
    script_name: str
    parent: str
    raw: int
    disc_size: int
    source_sha256: str
    output_sha256: str
    assets: list[dict]


class ArchiveReader:
    def names(self) -> list[str]:
        raise NotImplementedError

    def read(self, name: str) -> bytes:
        raise NotImplementedError


class ZipReader(ArchiveReader):
    def __init__(self, path: Path):
        self.path = path
        self.z = zipfile.ZipFile(path)

    def names(self) -> list[str]:
        return self.z.namelist()

    def read(self, name: str) -> bytes:
        return self.z.read(name)

    def close(self) -> None:
        self.z.close()


class DirectoryReader(ArchiveReader):
    def __init__(self, root: Path):
        self.root = root

    def names(self) -> list[str]:
        return [p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()]

    def read(self, name: str) -> bytes:
        return (self.root / PurePosixPath(name)).read_bytes()


def find_package_metadata(reader: ArchiveReader) -> list[PackageMetadata]:
    found: list[PackageMetadata] = []
    for name in reader.names():
        if not name.lower().endswith(".py") or "apply" not in PurePosixPath(name).name.lower():
            continue
        try:
            source = reader.read(name).decode("utf-8")
            vals = literal_assignments(source)
            assets = normalize_assets(vals.get("ASSETS"))
            raw = int(vals.get("RAW", RAW_DEFAULT))
            disc_size = int(vals.get("DISC_SIZE"))
            source_sha = str(vals.get("DISC_SHA")).lower()
            output_sha = str(vals.get("OUTPUT_SHA")).lower()
            if raw != RAW_DEFAULT or disc_size <= 0:
                continue
            if not HEX64.fullmatch(source_sha) or not HEX64.fullmatch(output_sha):
                continue
            found.append(PackageMetadata(name, str(PurePosixPath(name).parent), raw, disc_size, source_sha, output_sha, assets))
        except (UnicodeDecodeError, SyntaxError, ValueError, KeyError, TypeError):
            continue
    return found


def find_delta_set(reader: ArchiveReader, meta: PackageMetadata) -> tuple[str, list[dict]]:
    prefix = "" if meta.parent == "." else meta.parent.rstrip("/") + "/"
    candidates: list[tuple[str, list[dict]]] = []
    for name in reader.names():
        if not name.startswith(prefix) or not name.endswith("/MANIFEST.json"):
            continue
        try:
            data = json.loads(reader.read(name))
        except Exception:
            continue
        if not isinstance(data, list) or not data:
            continue
        required = {"lba", "original_sector_sha256", "patched_sector_sha256"}
        if all(isinstance(entry, dict) and required <= entry.keys() for entry in data):
            candidates.append((str(PurePosixPath(name).parent), data))
    if not candidates:
        raise ValueError(f"no sparse delta MANIFEST under {meta.parent}")
    candidates.sort(key=lambda item: len(item[1]), reverse=True)
    return candidates[0]


def read_source_sector(source: BinaryIO, lba: int, raw: int) -> bytes:
    source.seek(lba * raw)
    data = source.read(raw)
    if len(data) != raw:
        raise ValueError(f"truncated source sector {lba}")
    return data


def apply_delta_set(reader: ArchiveReader, delta_dir: str, manifest: list[dict], source: BinaryIO, raw: int) -> dict[int, bytes]:
    patched: dict[int, bytes] = {}
    for entry in manifest:
        lba = int(entry["lba"])
        if lba in patched:
            raise ValueError(f"duplicate LBA {lba}")
        original = read_source_sector(source, lba, raw)
        expected = str(entry["original_sector_sha256"]).lower()
        target = str(entry["patched_sector_sha256"]).lower()
        if sha_bytes(original) != expected:
            raise ValueError(f"LBA {lba} original sector SHA mismatch")
        delta_name = f"{delta_dir}/LBA{lba}.json"
        delta = json.loads(reader.read(delta_name))
        if int(delta["lba"]) != lba:
            raise ValueError(f"LBA {lba} delta LBA mismatch")
        if str(delta["original_sector_sha256"]).lower() != expected or str(delta["patched_sector_sha256"]).lower() != target:
            raise ValueError(f"LBA {lba} delta/manifest disagreement")
        sector = bytearray(original)
        occupied: list[tuple[int, int]] = []
        for span in delta["spans"]:
            offset = int(span["offset"])
            new = bytes.fromhex(span["data_hex"])
            end = offset + len(new)
            if offset < 0 or end > raw:
                raise ValueError(f"LBA {lba} span out of range")
            if any(not (end <= start or offset >= stop) for start, stop in occupied):
                raise ValueError(f"LBA {lba} overlapping spans")
            old = bytes(sector[offset:end])
            if sha_bytes(old) != str(span["old_sha256"]).lower():
                raise ValueError(f"LBA {lba} offset {offset} Expected Write mismatch")
            sector[offset:end] = new
            occupied.append((offset, end))
        result = bytes(sector)
        if sha_bytes(result) != target:
            raise ValueError(f"LBA {lba} patched sector SHA mismatch")
        patched[lba] = result
    return patched


def stream_candidate_sha(source: BinaryIO, disc_size: int, raw: int, patched: Mapping[int, bytes]) -> str:
    if disc_size % raw:
        raise ValueError("disc size is not raw-sector aligned")
    h = hashlib.sha256()
    source.seek(0)
    for lba in range(disc_size // raw):
        data = patched.get(lba)
        if data is None:
            data = source.read(raw)
        else:
            source.seek(raw, io.SEEK_CUR)
        if len(data) != raw:
            raise ValueError(f"truncated stream at LBA {lba}")
        h.update(data)
    return h.hexdigest()


def extract_asset(source: BinaryIO, patched: Mapping[int, bytes], lba: int, size: int, raw: int) -> bytes:
    output = bytearray()
    remaining = size
    sector = lba
    sync = b"\x00" + b"\xff" * 10 + b"\x00"
    while remaining:
        raw_sector = patched.get(sector)
        if raw_sector is None:
            raw_sector = read_source_sector(source, sector, raw)
        if raw_sector[:12] != sync or raw_sector[15] != 1:
            raise ValueError(f"LBA {sector} is not MODE1/2352")
        take = min(USER_SIZE, remaining)
        output += raw_sector[USER_OFFSET:USER_OFFSET + take]
        remaining -= take
        sector += 1
    return bytes(output)


def recover_one(source_path: Path, package_path: Path, output_dir: Path) -> dict:
    if package_path.is_dir():
        reader: ArchiveReader = DirectoryReader(package_path)
        close = None
    else:
        reader = ZipReader(package_path)
        close = reader.close
    try:
        metadata = find_package_metadata(reader)
        if not metadata:
            raise ValueError("no literal APPLY script contract found")
        source_size = source_path.stat().st_size
        source_sha = sha_file(source_path)
        errors: list[str] = []
        for meta in sorted(metadata, key=lambda item: len(item.assets), reverse=True):
            if source_size != meta.disc_size or source_sha != meta.source_sha256:
                errors.append(f"{meta.script_name}: source disc mismatch")
                continue
            try:
                delta_dir, manifest = find_delta_set(reader, meta)
                with source_path.open("rb") as source:
                    patched = apply_delta_set(reader, delta_dir, manifest, source, meta.raw)
                    candidate_sha = stream_candidate_sha(source, meta.disc_size, meta.raw, patched)
                    if candidate_sha != meta.output_sha256:
                        raise ValueError("whole candidate Disc SHA mismatch")
                    output_dir.mkdir(parents=True, exist_ok=True)
                    asset_rows = []
                    for asset in meta.assets:
                        data = extract_asset(source, patched, asset["lba"], asset["size"], meta.raw)
                        actual = sha_bytes(data)
                        if actual != asset["target_sha256"]:
                            raise ValueError(f"{asset['name']} re-extraction SHA mismatch")
                        path = output_dir / asset["filename"]
                        if path.exists() and path.read_bytes() != data:
                            raise ValueError(f"conflicting exact asset {path.name}")
                        path.write_bytes(data)
                        asset_rows.append({**asset, "reextracted_sha256": actual})
                return {
                    "status": "PASS_EXACT_SPARSE_PACKAGE_RECOVERY",
                    "package": str(package_path),
                    "package_sha256": sha_file(package_path) if package_path.is_file() else None,
                    "apply_contract": meta.script_name,
                    "delta_directory": delta_dir,
                    "source_disc_sha256": source_sha,
                    "candidate_disc_sha256": candidate_sha,
                    "changed_raw_sectors": len(patched),
                    "asset_count": len(asset_rows),
                    "assets": asset_rows,
                }
            except Exception as exc:
                errors.append(f"{meta.script_name}: {exc}")
        raise ValueError("; ".join(errors))
    finally:
        if close:
            close()


def selftest() -> dict:
    raw = RAW_DEFAULT
    sectors = 8
    disc = bytearray(sectors * raw)
    sync = b"\x00" + b"\xff" * 10 + b"\x00"
    for lba in range(sectors):
        base = lba * raw
        disc[base:base + 12] = sync
        disc[base + 15] = 1
        disc[base + 16:base + 16 + USER_SIZE] = bytes(((lba * 13 + index) & 255) for index in range(USER_SIZE))
    source_sha = sha_bytes(disc)
    lba = 2
    size = 3000
    old = bytes(disc[lba * raw:(lba + 1) * raw])
    new = bytearray(old)
    new[100:104] = b"TEST"
    candidate = bytearray(disc)
    candidate[lba * raw:(lba + 1) * raw] = new
    asset = bytes(new[16:16 + USER_SIZE]) + bytes(disc[(lba + 1) * raw + 16:(lba + 1) * raw + 16 + (size - USER_SIZE)])
    manifest = [{"lba": lba, "original_sector_sha256": sha_bytes(old), "patched_sector_sha256": sha_bytes(new)}]
    delta = {"lba": lba, "original_sector_sha256": sha_bytes(old), "patched_sector_sha256": sha_bytes(new), "spans": [{"offset": 100, "old_sha256": sha_bytes(old[100:104]), "data_hex": b"TEST".hex()}]}
    script = f"RAW={raw}\nDISC_SIZE={len(disc)}\nDISC_SHA='{source_sha}'\nOUTPUT_SHA='{sha_bytes(candidate)}'\nASSETS=[('A',{lba},{size},'{sha_bytes(asset)}')]\n"
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "source.bin"
        source.write_bytes(disc)
        package = root / "package.zip"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("P/APPLY_TEST_PATCH.py", script)
            archive.writestr("P/DELTA/MANIFEST.json", json.dumps(manifest))
            archive.writestr(f"P/DELTA/LBA{lba}.json", json.dumps(delta))
        result = recover_one(source, package, root / "out")
        passed = result["status"].startswith("PASS") and result["asset_count"] == 1 and (root / "out/A.MES").read_bytes() == asset
    return {"status": "PASS" if passed else "FAIL", "roundtrip": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    recover = sub.add_parser("recover")
    recover.add_argument("source_bin", type=Path)
    recover.add_argument("package", type=Path)
    recover.add_argument("--output-dir", type=Path, default=Path("output/SPARSE_PACKAGE_ASSETS"))
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else recover_one(args.source_bin, args.package, args.output_dir)
    if args.command == "recover":
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "SPARSE_PACKAGE_RECOVERY_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
