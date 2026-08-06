#!/usr/bin/env python3
"""Recover the exact 58/58 ST2 Disc 1 battle/static assets from retained real packages.

Inputs are the pristine MODE1/2352 Disc 1 BIN, the Batch137 55-asset delta package,
and the Batch110 package that retains the three exact PBOOK raw-sector payloads.
No package Python is executed. All metadata is parsed as literals and every write
is gated by source SHA-256, sector Expected Write SHA-256, patched sector SHA-256,
MODE1 EDC/ECC, whole-disc SHA-256, changed-sector accounting, and re-extraction.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

RAW = 2352
USER_OFFSET = 16
USER_SIZE = 2048
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
CHUNK = 8 * 1024 * 1024
SOURCE_SIZE = 659_293_824
SOURCE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
OUTPUT_SHA256 = "75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20"
B137_PACKAGE_SHA256 = "48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c"
B110_PACKAGE_SHA256 = "ed262a52b32c9a326edff85c1d7191ff7b46e3379771d973af536cf06c3103a3"
EXPECTED_CHANGED_SECTORS = 1626
PBOOK_NAMES = {"PBOOK_BT", "PBOOK_EC", "PBOOK_RC"}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def make_tables() -> tuple[list[int], list[int], list[int]]:
    forward = [0] * 256
    backward = [0] * 256
    edc_table = [0] * 256
    for value in range(256):
        doubled = ((value << 1) ^ (0x11D if value & 0x80 else 0)) & 0xFF
        forward[value] = doubled
        backward[value ^ doubled] = value
        x = value
        for _ in range(8):
            x = (x >> 1) ^ (0xD8018001 if x & 1 else 0)
        edc_table[value] = x & 0xFFFFFFFF
    return forward, backward, edc_table


F_LUT, B_LUT, EDC_LUT = make_tables()


def edc(data: bytes) -> int:
    result = 0
    for value in data:
        result = EDC_LUT[(result ^ value) & 0xFF] ^ (result >> 8)
    return result & 0xFFFFFFFF


def ecc(source: bytes, major_count: int, minor_count: int,
        major_mult: int, minor_inc: int) -> bytes:
    size = major_count * minor_count
    if len(source) < size:
        raise ValueError("short ECC source")
    output = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            value = source[index]
            index = (index + minor_inc) % size
            a ^= value
            b ^= value
            a = F_LUT[a]
        a = B_LUT[F_LUT[a] ^ b]
        output[major] = a
        output[major + major_count] = a ^ b
    return bytes(output)


def valid_mode1(sector: bytes) -> bool:
    return (
        len(sector) == RAW
        and sector[:12] == SYNC
        and sector[15] == 1
        and sector[2064:2068] == edc(sector[:2064]).to_bytes(4, "little")
        and sector[2068:2076] == b"\x00" * 8
        and sector[2076:2248] == ecc(sector[12:2076], 86, 24, 2, 86)
        and sector[2248:2352] == ecc(sector[12:2248], 52, 43, 86, 88)
    )


def literal_assignment(source: str, name: str) -> object:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise KeyError(f"literal assignment not found: {name}")


def read_sector(stream: BinaryIO, lba: int) -> bytes:
    stream.seek(lba * RAW)
    data = stream.read(RAW)
    if len(data) != RAW:
        raise ValueError(f"truncated sector LBA {lba}")
    return data


def apply_b137_delta(original: bytes, delta: bytes, lba: int) -> bytes:
    if len(delta) < 14 or delta[:8] != b"ST2B137D":
        raise ValueError(f"invalid B137 delta magic at LBA {lba}")
    embedded_lba, count = struct.unpack(">IH", delta[8:14])
    if embedded_lba != lba:
        raise ValueError(f"B137 delta LBA mismatch: {embedded_lba} != {lba}")
    output = bytearray(original)
    cursor = 14
    occupied: list[tuple[int, int]] = []
    for _ in range(count):
        if cursor + 4 > len(delta):
            raise ValueError(f"truncated B137 span header at LBA {lba}")
        offset, length = struct.unpack(">HH", delta[cursor:cursor + 4])
        cursor += 4
        end = offset + length
        if end > RAW or cursor + length > len(delta):
            raise ValueError(f"B137 span out of range at LBA {lba}")
        if any(not (end <= start or offset >= stop) for start, stop in occupied):
            raise ValueError(f"overlapping B137 spans at LBA {lba}")
        output[offset:end] = delta[cursor:cursor + length]
        cursor += length
        occupied.append((offset, end))
    if cursor != len(delta):
        raise ValueError(f"trailing B137 delta bytes at LBA {lba}")
    return bytes(output)


def extract_asset(path: Path, lba: int, size: int) -> bytes:
    output = bytearray()
    remaining = size
    with path.open("rb") as stream:
        while remaining:
            sector = read_sector(stream, lba)
            if sector[:12] != SYNC or sector[15] != 1:
                raise ValueError(f"asset sector is not MODE1/2352: LBA {lba}")
            take = min(USER_SIZE, remaining)
            output += sector[USER_OFFSET:USER_OFFSET + take]
            remaining -= take
            lba += 1
    return bytes(output)


def load_contracts(batch137: Path, batch110: Path) -> tuple[dict, list[dict], dict, dict]:
    if sha_file(batch137) != B137_PACKAGE_SHA256:
        raise ValueError("Batch137 package SHA-256 mismatch")
    if sha_file(batch110) != B110_PACKAGE_SHA256:
        raise ValueError("Batch110 package SHA-256 mismatch")
    with zipfile.ZipFile(batch137) as archive:
        manifest137 = json.loads(archive.read("BATCH137_DELTA_MANIFEST.json"))
        audit137 = list(csv.DictReader(
            archive.read("BATCH137_REEXTRACTION_AUDIT.csv").decode("utf-8-sig").splitlines()
        ))
    with zipfile.ZipFile(batch110) as archive:
        script = archive.read("batch110_apply_to_original_bin.py").decode("utf-8")
        manifest110 = literal_assignment(script, "M")
        assets110 = literal_assignment(script, "A")
    if not isinstance(manifest137, dict) or len(audit137) != 55:
        raise ValueError("Batch137 contract is not the 55-asset baseline")
    if not isinstance(manifest110, dict) or not isinstance(assets110, dict):
        raise ValueError("Batch110 literal contract is invalid")
    if PBOOK_NAMES - set(assets110):
        raise ValueError("Batch110 is missing a PBOOK asset contract")
    return manifest137, audit137, manifest110, assets110


def recover(source: Path, batch137: Path, batch110: Path,
            output_dir: Path, keep_disc: bool) -> dict:
    if source.stat().st_size != SOURCE_SIZE or sha_file(source) != SOURCE_SHA256:
        raise ValueError("pristine Disc 1 size/SHA-256 gate failed")
    manifest137, audit137, manifest110, assets110 = load_contracts(batch137, batch110)
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_disc = output_dir / "_BATCH200_BUILDING.bin"
    final_disc = output_dir / "Sakura_Taisen_2_Disc1_B200_BattleStatic58_Exact_KO.bin"
    assets_dir = output_dir / "EXACT_58_ASSETS"
    if temp_disc.exists() or final_disc.exists():
        raise FileExistsError("refusing to overwrite an existing Batch200 Disc output")
    shutil.copyfile(source, temp_disc)
    expected: dict[int, bytes] = {}
    original_edc_ecc = 0
    patched_edc_ecc = 0
    try:
        with zipfile.ZipFile(batch137) as archive, source.open("rb") as src, temp_disc.open("r+b") as dst:
            for lba_text, item in sorted(manifest137.items(), key=lambda row: int(row[0])):
                lba = int(lba_text)
                original = read_sector(src, lba)
                if sha_bytes(original) != str(item["original_sha256"]).lower():
                    raise ValueError(f"Batch137 Expected Write mismatch at LBA {lba}")
                delta = archive.read(str(item["file"]))
                if sha_bytes(delta) != str(item["delta_sha256"]).lower():
                    raise ValueError(f"Batch137 delta SHA mismatch at LBA {lba}")
                patched = apply_b137_delta(original, delta, lba)
                if sha_bytes(patched) != str(item["patched_sha256"]).lower():
                    raise ValueError(f"Batch137 patched sector SHA mismatch at LBA {lba}")
                if not valid_mode1(original) or not valid_mode1(patched):
                    raise ValueError(f"Batch137 MODE1 EDC/ECC failure at LBA {lba}")
                original_edc_ecc += 1
                patched_edc_ecc += 1
                expected[lba] = patched
                dst.seek(lba * RAW)
                dst.write(patched)
        with zipfile.ZipFile(batch110) as archive, source.open("rb") as src, temp_disc.open("r+b") as dst:
            for lba_text, item in sorted(manifest110.items(), key=lambda row: int(row[0])):
                if str(item["asset"]) not in PBOOK_NAMES:
                    continue
                lba = int(lba_text)
                if lba in expected:
                    raise ValueError(f"B137/B110 LBA collision at {lba}")
                original = read_sector(src, lba)
                payload = archive.read(str(item["file"]))
                if sha_bytes(original) != str(item["original_sha256"]).lower():
                    raise ValueError(f"Batch110 Expected Write mismatch at LBA {lba}")
                if len(payload) != RAW or sha_bytes(payload) != str(item["patched_sha256"]).lower():
                    raise ValueError(f"Batch110 payload SHA mismatch at LBA {lba}")
                if not valid_mode1(original) or not valid_mode1(payload):
                    raise ValueError(f"Batch110 MODE1 EDC/ECC failure at LBA {lba}")
                original_edc_ecc += 1
                patched_edc_ecc += 1
                expected[lba] = payload
                dst.seek(lba * RAW)
                dst.write(payload)
        if len(expected) != EXPECTED_CHANGED_SECTORS:
            raise ValueError(f"changed-sector contract mismatch: {len(expected)}")
        changed: set[int] = set()
        mismatched: list[int] = []
        with source.open("rb") as src, temp_disc.open("rb") as out:
            for lba in range(SOURCE_SIZE // RAW):
                before = src.read(RAW)
                after = out.read(RAW)
                if before != after:
                    changed.add(lba)
                if lba in expected and after != expected[lba]:
                    mismatched.append(lba)
        if changed != set(expected) or mismatched:
            raise ValueError("unregistered or mismatched sector changes detected")
        output_sha = sha_file(temp_disc)
        if output_sha != OUTPUT_SHA256:
            raise ValueError(f"whole Disc SHA mismatch: {output_sha}")
        assets_dir.mkdir(parents=True, exist_ok=True)
        asset_rows: list[dict] = []
        for row in audit137:
            name = str(row["asset"])
            lba = int(row["lba"])
            size = int(row["size"])
            target = str(row["expected_sha256"]).lower()
            data = extract_asset(temp_disc, lba, size)
            actual = sha_bytes(data)
            if actual != target:
                raise ValueError(f"{name} re-extraction SHA mismatch")
            suffix = ".CG" if name.startswith("PBOOK_") else ".MES"
            (assets_dir / f"{name}{suffix}").write_bytes(data)
            asset_rows.append({"name": name, "lba": lba, "size": size, "sha256": actual,
                               "source_batch": int(row["source_batch"])})
        for name in sorted(PBOOK_NAMES):
            spec = assets110[name]
            data = extract_asset(temp_disc, int(spec["lba"]), int(spec["size"]))
            actual = sha_bytes(data)
            if actual != str(spec["sha256"]).lower():
                raise ValueError(f"{name} re-extraction SHA mismatch")
            (assets_dir / f"{name}.CG").write_bytes(data)
            asset_rows.append({"name": name, "lba": int(spec["lba"]), "size": int(spec["size"]),
                               "sha256": actual, "source_batch": 110})
        if len(asset_rows) != 58 or len({row["name"] for row in asset_rows}) != 58:
            raise ValueError("58-asset uniqueness gate failed")
        result = {
            "batch": 200,
            "status": "PASS_REAL_FULL58_EXACT_RECOVERY",
            "source_disc_sha256": SOURCE_SHA256,
            "output_disc_sha256": output_sha,
            "changed_raw_sectors": len(changed),
            "unregistered_changed_sectors": 0,
            "sector_payload_mismatches": 0,
            "original_mode1_edc_ecc_pass": original_edc_ecc,
            "patched_mode1_edc_ecc_pass": patched_edc_ecc,
            "reextraction": "58/58 PASS",
            "assets_directory": str(assets_dir),
            "disc_retained": keep_disc,
            "inputs": {
                "batch137_package_sha256": B137_PACKAGE_SHA256,
                "batch110_package_sha256": B110_PACKAGE_SHA256,
            },
            "assets": sorted(asset_rows, key=lambda row: (row["lba"], row["name"])),
        }
        if keep_disc:
            temp_disc.replace(final_disc)
            result["output_disc"] = str(final_disc)
        else:
            temp_disc.unlink()
            result["output_disc"] = None
        (output_dir / "BATCH200_REAL_FULL58_RESULT.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return result
    except Exception:
        temp_disc.unlink(missing_ok=True)
        final_disc.unlink(missing_ok=True)
        raise


def selftest() -> dict:
    # Test the security-sensitive primitives without requiring copyrighted inputs.
    user = bytes((index * 7) & 0xFF for index in range(USER_SIZE))
    sector = bytearray(RAW)
    sector[:12] = SYNC
    sector[12:16] = b"\x00\x02\x00\x01"
    sector[16:2064] = user
    sector[2064:2068] = edc(sector[:2064]).to_bytes(4, "little")
    sector[2068:2076] = b"\x00" * 8
    sector[2076:2248] = ecc(sector[12:2076], 86, 24, 2, 86)
    sector[2248:2352] = ecc(sector[12:2248], 52, 43, 86, 88)
    original = bytes(sector)
    patch = b"TEST"
    delta = b"ST2B137D" + struct.pack(">IH", 3, 1) + struct.pack(">HH", 100, len(patch)) + patch
    modified = apply_b137_delta(original, delta, 3)
    literal = "M={'3': {'asset':'PBOOK_BT'}}\n"
    passed = (
        valid_mode1(original)
        and modified[100:104] == patch
        and literal_assignment(literal, "M") == {"3": {"asset": "PBOOK_BT"}}
        and sha_bytes(original) != sha_bytes(modified)
    )
    return {"status": "PASS" if passed else "FAIL", "primitive_roundtrip": passed}


def validate_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "batch": 200,
        "status": "PASS_REAL_FULL58_EXACT_RECOVERY",
        "source_disc_sha256": SOURCE_SHA256,
        "output_disc_sha256": OUTPUT_SHA256,
        "changed_raw_sectors": EXPECTED_CHANGED_SECTORS,
        "unregistered_changed_sectors": 0,
        "sector_payload_mismatches": 0,
        "original_mode1_edc_ecc_pass": EXPECTED_CHANGED_SECTORS,
        "patched_mode1_edc_ecc_pass": EXPECTED_CHANGED_SECTORS,
        "reextraction": "58/58 PASS",
    }
    for key, value in required.items():
        if data.get(key) != value:
            raise ValueError(f"manifest mismatch: {key}")
    assets = data.get("assets")
    if not isinstance(assets, list) or len(assets) != 58 or len({row["name"] for row in assets}) != 58:
        raise ValueError("manifest asset count/uniqueness mismatch")
    return {"status": "PASS", "assets": 58}


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("recover")
    run.add_argument("source_bin", type=Path)
    run.add_argument("batch137_package", type=Path)
    run.add_argument("batch110_package", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("output/BATCH200_FULL58"))
    run.add_argument("--keep-disc", action="store_true")
    commands.add_parser("selftest")
    validate = commands.add_parser("validate-manifest")
    validate.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.command == "recover":
        result = recover(args.source_bin, args.batch137_package, args.batch110_package,
                         args.output_dir, args.keep_disc)
    elif args.command == "validate-manifest":
        result = validate_manifest(args.manifest)
    else:
        result = selftest()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" or result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())