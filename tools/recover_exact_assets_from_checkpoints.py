#!/usr/bin/env python3
"""Recover exact ST2 assets from loose files, raw BIN checkpoints, or ZIPs.

Only assets whose complete SHA-256 equals a trusted target are emitted. Raw
MODE1/2352 checkpoints are decoded sector-by-sector from their 2,048-byte user
data areas; headers, EDC and ECC bytes are never mistaken for file payload.
Whole Disc images are never copied or modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

CHUNK = 8 * 1024 * 1024
MODE1_SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


def sha_stream(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    while block := stream.read(CHUNK):
        h.update(block)
    return h.hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files(root: Path) -> Iterable[Path]:
    return (path for path in root.rglob("*") if path.is_file())


def output_filename(asset: dict) -> str:
    configured = str(asset.get("filename", "")).strip()
    if configured:
        return Path(configured).name
    name = str(asset["name"])
    return name + (".CG" if name.startswith("PBOOK_") else ".MES")


def accept(data: bytes, asset: dict, output: Path, source: str, found: dict) -> bool:
    target = str(asset["target_sha256"]).lower()
    if len(data) != int(asset["size"]) or sha_bytes(data) != target:
        return False
    filename = output_filename(asset)
    path = output / filename
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"conflicting exact payload: {filename}")
    path.write_bytes(data)
    found[str(asset["name"])] = {
        "path": str(path),
        "filename": filename,
        "sha256": target,
        "source": source,
    }
    return True


def read_mode1_asset(
    stream: BinaryIO,
    lba: int,
    size: int,
    raw_sector_size: int,
    user_data_offset: int,
    user_data_size: int,
) -> bytes | None:
    output = bytearray()
    sector_index = 0
    while len(output) < size:
        stream.seek((lba + sector_index) * raw_sector_size)
        sector = stream.read(raw_sector_size)
        if len(sector) != raw_sector_size:
            return None
        if raw_sector_size == 2352:
            if sector[:12] != MODE1_SYNC or sector[15] != 1:
                return None
        end = user_data_offset + user_data_size
        if end > len(sector):
            return None
        output.extend(sector[user_data_offset:end])
        sector_index += 1
    return bytes(output[:size])


def scan_binary(
    stream: BinaryIO,
    label: str,
    assets: list[dict],
    disc: dict,
    output: Path,
    found: dict,
) -> None:
    raw = int(disc.get("raw_sector_size", 2352))
    user_offset = int(disc.get("user_data_offset", 16 if raw == 2352 else 0))
    user_size = int(disc.get("user_data_size", 2048 if raw == 2352 else raw))
    for asset in assets:
        if asset["name"] in found:
            continue
        data = read_mode1_asset(
            stream,
            int(asset["lba"]),
            int(asset["size"]),
            raw,
            user_offset,
            user_size,
        )
        if data is not None:
            accept(data, asset, output, f'{label}@LBA{asset["lba"]}', found)


def validate_manifest(manifest: dict) -> tuple[list[dict], dict]:
    assets = manifest.get("assets")
    disc = manifest.get("source_disc")
    if not isinstance(assets, list) or not assets:
        raise ValueError("manifest assets are missing")
    if not isinstance(disc, dict):
        raise ValueError("manifest source_disc is missing")
    names: set[str] = set()
    filenames: set[str] = set()
    for asset in assets:
        name = str(asset.get("name", ""))
        filename = output_filename(asset)
        target = str(asset.get("target_sha256", "")).lower()
        if not name or name in names:
            raise ValueError(f"duplicate or empty asset name: {name!r}")
        if not filename or filename in filenames:
            raise ValueError(f"duplicate or empty output filename: {filename!r}")
        if len(target) != 64 or any(ch not in "0123456789abcdef" for ch in target):
            raise ValueError(f"{name}: invalid target SHA")
        if int(asset.get("lba", -1)) < 0 or int(asset.get("size", 0)) <= 0:
            raise ValueError(f"{name}: invalid LBA or size")
        names.add(name)
        filenames.add(filename)
    if int(disc.get("size", 0)) <= 0:
        raise ValueError("invalid source disc size")
    return assets, disc


def recover(manifest_path: Path, root: Path, output: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets, disc = validate_manifest(manifest)
    output.mkdir(parents=True, exist_ok=True)
    found: dict[str, dict] = {}
    targets_by_size: dict[int, list[dict]] = {}
    for asset in assets:
        targets_by_size.setdefault(int(asset["size"]), []).append(asset)

    for path in files(root):
        try:
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as archive:
                    for info in archive.infolist():
                        if info.is_dir():
                            continue
                        if info.file_size in targets_by_size:
                            data = archive.read(info)
                            for asset in targets_by_size[info.file_size]:
                                accept(data, asset, output, f"{path}!{info.filename}", found)
                        elif info.file_size == int(disc["size"]):
                            with archive.open(info) as member:
                                if member.seekable():
                                    scan_binary(member, f"{path}!{info.filename}", assets, disc, output, found)
                                else:
                                    with tempfile.TemporaryFile() as temporary:
                                        while block := member.read(CHUNK):
                                            temporary.write(block)
                                        temporary.seek(0)
                                        scan_binary(
                                            temporary,
                                            f"{path}!{info.filename}",
                                            assets,
                                            disc,
                                            output,
                                            found,
                                        )
            else:
                size = path.stat().st_size
                if size in targets_by_size:
                    data = path.read_bytes()
                    for asset in targets_by_size[size]:
                        accept(data, asset, output, str(path), found)
                elif size == int(disc["size"]):
                    with path.open("rb") as stream:
                        scan_binary(stream, str(path), assets, disc, output, found)
        except (OSError, zipfile.BadZipFile):
            continue

    missing = [asset["name"] for asset in assets if asset["name"] not in found]
    result = {
        "status": "PASS_ALL_EXACT_ASSETS_RECOVERED" if not missing else "PARTIAL_EXACT_ASSET_RECOVERY",
        "recovered": found,
        "missing": missing,
        "recovered_count": len(found),
        "target_count": len(assets),
        "raw_mode": {
            "raw_sector_size": int(disc.get("raw_sector_size", 2352)),
            "user_data_offset": int(disc.get("user_data_offset", 16)),
            "user_data_size": int(disc.get("user_data_size", 2048)),
        },
    }
    (output / "RECOVERY_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def make_mode1_sector(user_data: bytes, raw: int = 2352) -> bytes:
    if len(user_data) != 2048 or raw != 2352:
        raise ValueError("self-test expects MODE1/2352")
    sector = bytearray(raw)
    sector[:12] = MODE1_SYNC
    sector[12:15] = b"\x00\x02\x00"
    sector[15] = 1
    sector[16:2064] = user_data
    return bytes(sector)


def selftest() -> dict:
    raw = 2352
    sectors = 12
    asset_a = bytes((index * 7 + 3) & 255 for index in range(3000))
    asset_b = bytes((index * 11 + 5) & 255 for index in range(1900))
    disc = bytearray()
    user_sectors = [bytearray(2048) for _ in range(sectors)]
    for offset, value in enumerate(asset_a):
        absolute = offset
        user_sectors[2 + absolute // 2048][absolute % 2048] = value
    for user_data in user_sectors:
        disc.extend(make_mode1_sector(bytes(user_data)))
    manifest = {
        "source_disc": {
            "size": len(disc),
            "raw_sector_size": raw,
            "user_data_offset": 16,
            "user_data_size": 2048,
        },
        "assets": [
            {
                "name": "PBOOK_BT",
                "filename": "PBOOK_BT.CG",
                "lba": 2,
                "size": len(asset_a),
                "target_sha256": sha_bytes(asset_a),
            },
            {
                "name": "SYS20",
                "filename": "SYS20.MES",
                "lba": 5,
                "size": len(asset_b),
                "target_sha256": sha_bytes(asset_b),
            },
        ],
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "checkpoint.bin").write_bytes(disc)
        with zipfile.ZipFile(root / "loose.zip", "w") as archive:
            archive.writestr("nested/SYS20.MES", asset_b)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        result = recover(manifest_path, root, root / "output")
        passed = (
            result["status"] == "PASS_ALL_EXACT_ASSETS_RECOVERED"
            and (root / "output/PBOOK_BT.CG").read_bytes() == asset_a
            and (root / "output/SYS20.MES").read_bytes() == asset_b
        )
    return {"status": "PASS" if passed else "FAIL", "roundtrip": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("recover")
    run.add_argument("manifest", type=Path)
    run.add_argument("root", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("output/EXACT_ASSETS"))
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else recover(
        args.manifest, args.root, args.output_dir
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
