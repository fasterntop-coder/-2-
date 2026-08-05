#!/usr/bin/env python3
"""Recover a historical exact raw-sector patch from its apply-script manifest.

The historical script is never executed. Top-level literal assignments are read
with AST, exact patched sectors are recovered from loose files, ZIP members or a
whole verified output BIN, and a new BIN is emitted only after source-sector and
whole-output SHA gates pass.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, BinaryIO, Iterable

CHUNK = 8 * 1024 * 1024


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_stream(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    while block := stream.read(CHUNK):
        h.update(block)
    return h.hexdigest()


def hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hash_stream(stream)


def literal_assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    values: dict[str, Any] = {}
    for node in tree.body:
        target = None
        value_node = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value_node = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value_node = node.target.id, node.value
        if target is None or value_node is None:
            continue
        try:
            values[target] = ast.literal_eval(value_node)
        except Exception:
            if isinstance(value_node, ast.Name) and value_node.id in values:
                values[target] = values[value_node.id]
    return values


def pick(values: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in values:
            return values[name]
    return default


def load_manifest(path: Path) -> dict[str, Any]:
    values = literal_assignments(path)
    sectors = pick(values, "SECTORS", "M")
    if not isinstance(sectors, dict) or not sectors:
        raise ValueError("literal SECTORS/M manifest not found")
    normalized: dict[str, dict[str, str]] = {}
    for key, item in sectors.items():
        if not isinstance(item, dict):
            raise ValueError(f"invalid sector manifest at {key}")
        lba = str(int(key))
        original = str(item.get("original_sha256", item.get("OriginalSha", ""))).lower()
        patched = str(item.get("patched_sha256", item.get("PatchedSha", ""))).lower()
        if len(original) != 64 or len(patched) != 64:
            raise ValueError(f"missing SHA gate at LBA {lba}")
        normalized[lba] = {
            "original_sha256": original,
            "patched_sha256": patched,
            "asset": str(item.get("asset", "")),
        }
    return {
        "source_size": int(pick(values, "SOURCE_SIZE", "SIZE", default=0)),
        "source_sha256": str(pick(values, "SOURCE_SHA", "SS", default="")).lower(),
        "output_sha256": str(pick(values, "OUTPUT_SHA", "OS", default="")).lower(),
        "raw_sector": int(pick(values, "RS", "RAW", "RAW_SECTOR", default=2352)),
        "sector_count": len(normalized),
        "sectors": normalized,
    }


def files(root: Path) -> Iterable[Path]:
    return (p for p in root.rglob("*") if p.is_file())


def exact_loose_image(root: Path, size: int, digest: str) -> Path | None:
    for path in files(root):
        if path.suffix.lower() == ".bin" and path.stat().st_size == size and hash_file(path) == digest:
            return path
    return None


def exact_zip_image(root: Path, size: int, digest: str, temp: Path) -> Path | None:
    for path in files(root):
        if path.suffix.lower() != ".zip":
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if info.is_dir() or info.file_size != size:
                        continue
                    with archive.open(info) as member:
                        if hash_stream(member) != digest:
                            continue
                    output = temp / Path(info.filename).name
                    with archive.open(info) as source, output.open("wb") as target:
                        shutil.copyfileobj(source, target, CHUNK)
                    return output
        except (zipfile.BadZipFile, OSError):
            continue
    return None


def find_image(root: Path, size: int, digest: str, temp: Path) -> Path | None:
    return exact_loose_image(root, size, digest) or exact_zip_image(root, size, digest, temp)


def recover_loose_sectors(root: Path, manifest: dict[str, Any], output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    raw = manifest["raw_sector"]
    wanted = {item["patched_sha256"]: lba for lba, item in manifest["sectors"].items()}
    recovered = 0
    for path in files(root):
        if path.stat().st_size != raw:
            continue
        digest = hash_file(path)
        if digest in wanted:
            lba = wanted[digest]
            target = output / f"PATCHED_SECTOR_LBA{lba}.bin"
            if not target.exists():
                shutil.copyfile(path, target)
                recovered += 1
    return recovered


def harvest_image(image: Path, manifest: dict[str, Any], output: Path) -> None:
    raw = manifest["raw_sector"]
    output.mkdir(parents=True, exist_ok=True)
    with image.open("rb") as stream:
        for lba_text, item in manifest["sectors"].items():
            stream.seek(int(lba_text) * raw)
            sector = stream.read(raw)
            if hash_bytes(sector) != item["patched_sha256"]:
                raise RuntimeError(f"patched image sector mismatch LBA {lba_text}")
            (output / f"PATCHED_SECTOR_LBA{lba_text}.bin").write_bytes(sector)


def missing_payloads(manifest: dict[str, Any], output: Path) -> list[int]:
    raw = manifest["raw_sector"]
    missing: list[int] = []
    for lba_text, item in manifest["sectors"].items():
        path = output / f"PATCHED_SECTOR_LBA{lba_text}.bin"
        if not path.exists() or path.stat().st_size != raw or hash_file(path) != item["patched_sha256"]:
            missing.append(int(lba_text))
    return missing


def apply(source: Path, destination: Path, manifest: dict[str, Any], payloads: Path) -> str:
    if source.stat().st_size != manifest["source_size"] or hash_file(source) != manifest["source_sha256"]:
        raise RuntimeError("source BIN size/SHA gate failed")
    raw = manifest["raw_sector"]
    shutil.copyfile(source, destination)
    try:
        with source.open("rb") as original, destination.open("r+b") as patched:
            for lba_text, item in manifest["sectors"].items():
                lba = int(lba_text)
                original.seek(lba * raw)
                before = original.read(raw)
                if hash_bytes(before) != item["original_sha256"]:
                    raise RuntimeError(f"Expected Write failed at LBA {lba}")
                payload = (payloads / f"PATCHED_SECTOR_LBA{lba}.bin").read_bytes()
                if len(payload) != raw or hash_bytes(payload) != item["patched_sha256"]:
                    raise RuntimeError(f"payload gate failed at LBA {lba}")
                patched.seek(lba * raw)
                patched.write(payload)
        digest = hash_file(destination)
        if digest != manifest["output_sha256"]:
            raise RuntimeError(f"whole output SHA mismatch: {digest}")
        return digest
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def package(manifest: dict[str, Any], payloads: Path, output: Path) -> str:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("PATCH_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for lba in sorted(manifest["sectors"], key=int):
            path = payloads / f"PATCHED_SECTOR_LBA{lba}.bin"
            archive.write(path, f"PATCH_SECTORS/{path.name}")
    return hash_file(output)


def recover(script: Path, root: Path, output: Path) -> dict[str, Any]:
    manifest = load_manifest(script)
    output.mkdir(parents=True, exist_ok=True)
    payloads = output / "PATCH_SECTORS"
    temp = output / "_TEMP"
    temp.mkdir(exist_ok=True)
    (output / "NORMALIZED_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    recover_loose_sectors(root, manifest, payloads)
    missing = missing_payloads(manifest, payloads)
    if missing:
        historical = find_image(root, manifest["source_size"], manifest["output_sha256"], temp)
        if historical:
            harvest_image(historical, manifest, payloads)
    missing = missing_payloads(manifest, payloads)
    if missing:
        result = {"status": "BLOCKED_PATCH_BYTES_NOT_FOUND", "missing_count": len(missing), "missing_lbas": missing}
    else:
        patch_zip = output / f"EXACT_{manifest['sector_count']}_SECTOR_PATCH.zip"
        patch_zip_sha = package(manifest, payloads, patch_zip)
        source = find_image(root, manifest["source_size"], manifest["source_sha256"], temp)
        if source:
            target = output / "Sakura_Taisen_2_Disc1_EXACT_KO.bin"
            target_sha = apply(source, target, manifest, payloads)
            result = {"status": "PASS_EXACT_BIN_CREATED", "output_bin": str(target), "output_sha256": target_sha,
                      "sector_count": manifest["sector_count"], "patch_zip": str(patch_zip), "patch_zip_sha256": patch_zip_sha}
        else:
            result = {"status": "PASS_EXACT_PATCH_PACKAGE_RECOVERED_SOURCE_BIN_PENDING",
                      "sector_count": manifest["sector_count"], "patch_zip": str(patch_zip), "patch_zip_sha256": patch_zip_sha}
    (output / "RECOVERY_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def selftest() -> dict[str, Any]:
    raw, sectors = 64, 10
    source = bytearray((i * 13 + 7) & 0xFF for i in range(raw * sectors))
    target = bytearray(source)
    entries: dict[str, dict[str, str]] = {}
    for lba in (2, 6, 8):
        before = bytes(source[lba * raw:(lba + 1) * raw])
        after = bytearray(before)
        after[5:17] = bytes(x ^ (lba + 19) for x in after[5:17])
        target[lba * raw:(lba + 1) * raw] = after
        entries[str(lba)] = {"original_sha256": hash_bytes(before), "patched_sha256": hash_bytes(after), "asset": "TEST"}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_path, target_path = root / "source.bin", root / "target.bin"
        source_path.write_bytes(source); target_path.write_bytes(target)
        script = root / "apply.py"
        script.write_text(f"SOURCE_SIZE={len(source)}\nSOURCE_SHA='{hash_bytes(source)}'\nOUTPUT_SHA='{hash_bytes(target)}'\nRS={raw}\nSECTORS={entries!r}\n", encoding="utf-8")
        result = recover(script, root, root / "output")
        built = root / "output" / "Sakura_Taisen_2_Disc1_EXACT_KO.bin"
        passed = result["status"] == "PASS_EXACT_BIN_CREATED" and built.read_bytes() == target
    return {"status": "PASS" if passed else "FAIL", "roundtrip": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("recover")
    run.add_argument("manifest_script", type=Path)
    run.add_argument("search_root", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("output/EXACT_RECOVERY"))
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else recover(args.manifest_script, args.search_root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
