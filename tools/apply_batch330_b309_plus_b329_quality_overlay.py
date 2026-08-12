#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RAW = 2352
USER = 2048
USER_OFF = 16
EXPECTED_PARENT = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
ASSETS = [
    {
        "path": "SAKURA2/EV00060.MES",
        "lba": 247407,
        "size": 72656,
        "source_sha256": "f26295cffa37706af3792d194c39384e634565029ab2e0c5348153a8966c641d",
        "replacement_sha256": "8d6b79d3b120d0af68437c5a5fe9834aae66a5bcfacee3f7b6cb005a092f2fbd",
    },
    {
        "path": "SAKURA2/EV00002.MES",
        "lba": 247457,
        "size": 71798,
        "source_sha256": "07e4f2272b0cc5755f89e1b1c50bb641ac9da8e0c600ca8d8a989f8f392c5708",
        "replacement_sha256": "5e82fa4fca18eb189b8cf2b6eb6fd80faf79053ddfc735a373d1067894e74752",
    },
]
SYNC = bytes([0] + [0xFF] * 10 + [0])


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def edc_lut() -> list[int]:
    table = []
    for i in range(256):
        v = i
        for _ in range(8):
            v = (v >> 1) ^ (0xD8018001 if v & 1 else 0)
        table.append(v & 0xFFFFFFFF)
    return table


def ecc_luts() -> tuple[list[int], list[int]]:
    f = [0] * 256
    b = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        f[i] = j & 0xFF
        b[i ^ f[i]] = i
    return f, b


EDC = edc_lut()
ECC_F, ECC_B = ecc_luts()


def calc_edc(data: bytes) -> int:
    value = 0
    for byte in data:
        value = (value >> 8) ^ EDC[(value ^ byte) & 0xFF]
    return value & 0xFFFFFFFF


def ecc(src: bytes, major_count: int, minor_count: int, major_mult: int, minor_inc: int) -> bytes:
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            temp = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= temp
            b ^= temp
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b
    return bytes(out)


def rebuild_mode1(sec: bytearray) -> None:
    if len(sec) != RAW or sec[:12] != SYNC or sec[15] != 1:
        raise ValueError("not MODE1/2352")
    sec[0x810:0x814] = calc_edc(sec[:0x810]).to_bytes(4, "little")
    sec[0x814:0x81C] = bytes(8)
    sec[0x81C:0x8C8] = ecc(sec[0x0C:0x81C], 86, 24, 2, 86)
    sec[0x8C8:0x930] = ecc(sec[0x0C:0x8C8], 52, 43, 86, 88)


def verify_mode1(sec: bytes) -> bool:
    if len(sec) != RAW or sec[:12] != SYNC or sec[15] != 1:
        return False
    if int.from_bytes(sec[0x810:0x814], "little") != calc_edc(sec[:0x810]):
        return False
    if sec[0x814:0x81C] != bytes(8):
        return False
    p = ecc(sec[0x0C:0x81C], 86, 24, 2, 86)
    if sec[0x81C:0x8C8] != p:
        return False
    return sec[0x8C8:0x930] == ecc(sec[0x0C:0x8C8], 52, 43, 86, 88)


def extract_asset(f, lba: int, size: int) -> bytes:
    out = bytearray()
    sectors = (size + USER - 1) // USER
    for i in range(sectors):
        f.seek((lba + i) * RAW)
        sec = f.read(RAW)
        if len(sec) != RAW:
            raise ValueError("short sector read")
        if sec[:12] != SYNC or sec[15] != 1:
            raise ValueError(f"LBA {lba+i} is not MODE1/2352")
        out.extend(sec[USER_OFF:USER_OFF + USER])
    return bytes(out[:size])


def patch_asset(f, lba: int, payload: bytes) -> list[int]:
    sectors = (len(payload) + USER - 1) // USER
    changed: list[int] = []
    for i in range(sectors):
        off = (lba + i) * RAW
        f.seek(off)
        original = f.read(RAW)
        if len(original) != RAW:
            raise ValueError("short sector read")
        sec = bytearray(original)
        if sec[:12] != SYNC or sec[15] != 1:
            raise ValueError(f"LBA {lba+i} is not MODE1/2352")
        begin = i * USER
        piece = payload[begin:begin + USER]
        sec[USER_OFF:USER_OFF + len(piece)] = piece
        rebuild_mode1(sec)
        if not verify_mode1(bytes(sec)):
            raise ValueError(f"LBA {lba+i}: rebuilt sector failed EDC/ECC")
        if bytes(sec) != original:
            changed.append(lba + i)
            f.seek(off)
            f.write(sec)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply Batch329 replacements to the exact Batch309 Disc1 candidate")
    ap.add_argument("parent_bin", type=Path)
    ap.add_argument("replacement_dir", type=Path, help="Directory containing SAKURA2/EV00002.MES and EV00060.MES")
    ap.add_argument("output_bin", type=Path)
    ap.add_argument("--expected-parent-sha256", default=EXPECTED_PARENT)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    parent_sha = sha_file(args.parent_bin)
    if parent_sha.lower() != args.expected_parent_sha256.lower():
        raise SystemExit(f"parent SHA mismatch: {parent_sha}")

    with args.parent_bin.open("rb") as f:
        for asset in ASSETS:
            current = extract_asset(f, int(asset["lba"]), int(asset["size"]))
            if sha(current) != asset["source_sha256"]:
                raise SystemExit(f"parent asset mismatch: {asset['path']} {sha(current)}")
            replacement = (args.replacement_dir / str(asset["path"])).read_bytes()
            if len(replacement) != asset["size"] or sha(replacement) != asset["replacement_sha256"]:
                raise SystemExit(f"replacement mismatch: {asset['path']}")

    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.parent_bin, args.output_bin)
    changed: list[int] = []
    with args.output_bin.open("r+b") as f:
        for asset in ASSETS:
            replacement = (args.replacement_dir / str(asset["path"])).read_bytes()
            changed.extend(patch_asset(f, int(asset["lba"]), replacement))
        for asset in ASSETS:
            got = extract_asset(f, int(asset["lba"]), int(asset["size"]))
            if sha(got) != asset["replacement_sha256"]:
                raise SystemExit(f"post-write re-extraction mismatch: {asset['path']}")

    changed = sorted(set(changed))
    output_sha = sha_file(args.output_bin)
    report = {
        "format": "ST2-CD1-BATCH330-B309-PLUS-B329-QUALITY-OVERLAY-v1",
        "batch": 330,
        "status": "PASS_MATERIALIZED_CHILD_CANDIDATE",
        "parent_sha256": parent_sha,
        "output_sha256": output_sha,
        "replacement_files": 2,
        "corrected_records": 3,
        "changed_raw_sectors_vs_parent": len(changed),
        "changed_lbas_vs_parent": changed,
        "all_written_sectors_mode1_edc_ecc": True,
        "asset_reextraction": "2/2 PASS",
        "guessed_bytes": 0,
        "assets": ASSETS,
    }
    report_path = args.report or args.output_bin.with_suffix(args.output_bin.suffix + ".batch330.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
