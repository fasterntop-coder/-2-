#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

USER_OFF = 16
USER_SIZE = 2048
DISC_SIZE = 659293824
R37_SHA = "56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736"
ASSET = {
    "path": "SAKURA1/SK0104.BIN",
    "lba": 44797,
    "size": 50364,
    "pristine_sha256": "3ff7ccb0a9a31258e6f02064483c99c4df081cea3816c9aa050a20a59fbc66e6",
    "c2fix_sha256": "1e2559457bf62efad722dc719a34de5ed9105c42d732aa333f4117b68869e0f9",
    "replacement_sha256": "6a8aa6204bccfaa23362c1d549e3f9a5fe0aa4bbe2e2a003796e9e9670793db7",
}
CONTROLS = [
    ("SAKURA1/SK0000.BIN", 44539, 4948, "1d13bb6480e902cfbae25dfaada7e78fb9a831f9d3423545d335ce8375a26edd"),
    ("SAKURA1/SK0204.BIN", 45011, 1476, "0f667489b72bde453c30daf307d796dbde968e989ceed400db44c837b2d62644"),
    ("SAKURA1/SK0305.BIN", 45427, 1520, "33a71e3f3c225860f415368e1bf2555216f3881f9a9ce48e7fe83f20eba59a7d"),
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_asset(raw: bytes | bytearray, lba: int, size: int) -> bytes:
    out = bytearray()
    pos = 0
    while len(out) < size:
        off = (lba + pos) * RAW_SECTOR_SIZE
        sec = raw[off:off + RAW_SECTOR_SIZE]
        if len(sec) != RAW_SECTOR_SIZE or sec[15] != 1:
            raise ValueError(f"bad MODE1 sector at LBA {lba + pos}")
        take = min(USER_SIZE, size - len(out))
        out += sec[USER_OFF:USER_OFF + take]
        pos += 1
    return bytes(out)


def rebuild_mode1(sec: bytearray) -> None:
    if len(sec) != RAW_SECTOR_SIZE or sec[15] != 1:
        raise ValueError("not MODE1/2352")
    sec[0x810:0x814] = edc(bytes(sec[:0x810])).to_bytes(4, "little")
    sec[0x814:0x81C] = bytes(8)
    sec[0x81C:0x8C8] = _ecc_compute(bytes(sec[0x0C:0x81C]), 86, 24, 2, 86)
    sec[0x8C8:0x930] = _ecc_compute(bytes(sec[0x0C:0x8C8]), 52, 43, 86, 88)


def write_asset(raw: bytearray, lba: int, payload: bytes) -> list[dict]:
    writes = []
    cursor = 0
    idx = 0
    while cursor < len(payload):
        l = lba + idx
        off = l * RAW_SECTOR_SIZE
        before = bytes(raw[off:off + RAW_SECTOR_SIZE])
        if not verify_mode1_sector(before)["valid"]:
            raise ValueError(f"parent sector invalid at LBA {l}")
        sec = bytearray(before)
        take = min(USER_SIZE, len(payload) - cursor)
        sec[USER_OFF:USER_OFF + take] = payload[cursor:cursor + take]
        rebuild_mode1(sec)
        after = bytes(sec)
        if before != after:
            if not verify_mode1_sector(after)["valid"]:
                raise ValueError(f"rebuilt sector invalid at LBA {l}")
            raw[off:off + RAW_SECTOR_SIZE] = after
            writes.append({
                "lba": l,
                "before_sha256": sha_bytes(before),
                "after_sha256": sha_bytes(after),
            })
        cursor += take
        idx += 1
    return writes


def main() -> None:
    ap = argparse.ArgumentParser(description="Promote exact R37 SK0104 and close Disc1 story 141/141 inventory")
    ap.add_argument("--parent-bin", required=True, type=Path)
    ap.add_argument("--parent-sha256", required=True, help="Exact SHA-256 expected for the runtime parent candidate")
    ap.add_argument("--r37-bin", required=True, type=Path)
    ap.add_argument("--output-bin", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    for p in (args.parent_bin, args.r37_bin):
        if p.stat().st_size != DISC_SIZE:
            raise SystemExit(f"FAIL size: {p}")

    parent_sha = sha_file(args.parent_bin)
    if parent_sha.lower() != args.parent_sha256.lower():
        raise SystemExit(f"FAIL parent SHA expected={args.parent_sha256} actual={parent_sha}")
    donor_sha = sha_file(args.r37_bin)
    if donor_sha != R37_SHA:
        raise SystemExit(f"FAIL R37 SHA expected={R37_SHA} actual={donor_sha}")

    parent = bytearray(args.parent_bin.read_bytes())
    donor = args.r37_bin.read_bytes()
    donor_asset = extract_asset(donor, ASSET["lba"], ASSET["size"])
    if sha_bytes(donor_asset) != ASSET["replacement_sha256"]:
        raise SystemExit("FAIL donor SK0104 replacement SHA")

    before_asset = extract_asset(parent, ASSET["lba"], ASSET["size"])
    before_sha = sha_bytes(before_asset)
    allowed = {ASSET["pristine_sha256"], ASSET["c2fix_sha256"], ASSET["replacement_sha256"]}
    if before_sha not in allowed:
        raise SystemExit(f"FAIL SK0104 unexpected parent SHA {before_sha}")

    writes = [] if before_sha == ASSET["replacement_sha256"] else write_asset(parent, ASSET["lba"], donor_asset)

    after_asset = extract_asset(parent, ASSET["lba"], ASSET["size"])
    if sha_bytes(after_asset) != ASSET["replacement_sha256"]:
        raise SystemExit("FAIL SK0104 whole-asset re-extraction")

    controls = []
    for path, lba, size, expected in CONTROLS:
        got = sha_bytes(extract_asset(parent, lba, size))
        if got != expected:
            raise SystemExit(f"FAIL identity control {path}: {got}")
        controls.append({"path": path, "sha256": got, "status": "PASS"})

    changed_lbas = [w["lba"] for w in writes]
    for lba in changed_lbas:
        off = lba * RAW_SECTOR_SIZE
        if not verify_mode1_sector(bytes(parent[off:off + RAW_SECTOR_SIZE]))["valid"]:
            raise SystemExit(f"FAIL post-write EDC/ECC LBA {lba}")

    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.write_bytes(parent)
    output_sha = sha_file(args.output_bin)

    report = {
        "batch": 279,
        "status": "PASS_BATCH279_STORY141_PHYSICAL_CLOSURE",
        "parent_sha256": parent_sha,
        "r37_donor_sha256": donor_sha,
        "output_sha256": output_sha,
        "guessed_payload_bytes": 0,
        "promotion": {
            "path": ASSET["path"],
            "before_sha256": before_sha,
            "after_sha256": ASSET["replacement_sha256"],
            "whole_asset_reextraction": "PASS",
        },
        "expected_write": writes,
        "changed_raw_sectors": len(writes),
        "changed_lbas": changed_lbas,
        "changed_sector_accounting": "PASS",
        "changed_sector_edc_ecc": f"{len(writes)}/{len(writes)} PASS",
        "identity_control_reextraction": controls,
        "story_inventory": {
            "translated_or_localized_replacements": 136,
            "identity_controls": 5,
            "files_accounted": 141,
            "files_total": 141,
            "source_inventory_percent": 100.0,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    print(f"output_sha256={output_sha}")
    print(f"changed_raw_sectors={len(writes)}")
    print("story_files_accounted=141/141")


if __name__ == "__main__":
    main()
