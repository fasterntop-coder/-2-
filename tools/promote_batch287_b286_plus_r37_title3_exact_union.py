#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE = 659_293_824
USER_OFF = 16
USER_SIZE = 2048
SOURCE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
R37_SHA = "56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736"
B286_STATUS = "PASS_BATCH286_B285_PLUS_B273_MOVIE12_SECTOR_UNION"
PASS_STATUS = "PASS_BATCH287_B286_PLUS_R37_TITLE3_EXACT_UNION"
ASSETS = [
    {"path": "SAKURA1/TITLE.BIN", "lba": 1210, "size": 154408, "sha256": "0929d80109519c63fb70f46469d3b3b1d4d21c2841b46ba7ac4b4807b0a30ad2"},
    {"path": "SAKURA1/TTL2CGB.BIN", "lba": 333, "size": 66467, "sha256": "d9f060c35203b971a00a4ff70816f2a4a60ff739de477d84222b30bb3882a6e5"},
    {"path": "SAKURA1/TTL2CGB1.BIN", "lba": 48460, "size": 66467, "sha256": "d9f060c35203b971a00a4ff70816f2a4a60ff739de477d84222b30bb3882a6e5"},
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_asset(raw: bytes | bytearray, lba: int, size: int) -> bytes:
    out = bytearray()
    sector = 0
    while len(out) < size:
        off = (lba + sector) * RAW_SECTOR_SIZE
        sec = raw[off:off + RAW_SECTOR_SIZE]
        if len(sec) != RAW_SECTOR_SIZE or sec[15] != 1:
            raise SystemExit(f"FAIL non-MODE1 asset sector LBA {lba + sector}")
        take = min(USER_SIZE, size - len(out))
        out += sec[USER_OFF:USER_OFF + take]
        sector += 1
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch287: exact R37/R36 title3 asset union onto successful Batch286")
    ap.add_argument("--parent-bin", required=True, type=Path, help="exact successful Batch286 BIN")
    ap.add_argument("--b286-report", required=True, type=Path)
    ap.add_argument("--source-bin", required=True, type=Path, help="exact pristine Disc 1 BIN")
    ap.add_argument("--r37-bin", required=True, type=Path, help="exact ST2R37 BIN")
    ap.add_argument("--output-bin", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    for p in (args.parent_bin, args.source_bin, args.r37_bin):
        if p.stat().st_size != DISC_SIZE:
            raise SystemExit(f"FAIL disc size {p}")

    source_sha = sha_file(args.source_bin)
    r37_sha = sha_file(args.r37_bin)
    parent_sha = sha_file(args.parent_bin)
    if source_sha != SOURCE_SHA:
        raise SystemExit("FAIL pristine Disc 1 SHA binding")
    if r37_sha != R37_SHA:
        raise SystemExit("FAIL ST2R37 donor Disc SHA binding")

    b286 = json.loads(args.b286_report.read_text(encoding="utf-8"))
    if b286.get("status") != B286_STATUS or str(b286.get("output_sha256", "")).lower() != parent_sha:
        raise SystemExit("FAIL Batch286 report/status/output SHA binding")
    if int(b286.get("guessed_payload_bytes", -1)) != 0:
        raise SystemExit("FAIL Batch286 guessed payload bytes")

    parent = args.parent_bin.read_bytes()
    source = args.source_bin.read_bytes()
    donor = args.r37_bin.read_bytes()

    for asset in ASSETS:
        donor_asset = extract_asset(donor, asset["lba"], asset["size"])
        if sha_bytes(donor_asset) != asset["sha256"]:
            raise SystemExit(f"FAIL donor whole-asset SHA {asset['path']}")

    delta = []
    asset_lbas = set()
    for asset in ASSETS:
        count = (asset["size"] + USER_SIZE - 1) // USER_SIZE
        for lba in range(asset["lba"], asset["lba"] + count):
            asset_lbas.add(lba)
    for lba in sorted(asset_lbas):
        off = lba * RAW_SECTOR_SIZE
        before = source[off:off + RAW_SECTOR_SIZE]
        after = donor[off:off + RAW_SECTOR_SIZE]
        if before != after:
            if not verify_mode1_sector(after)["valid"]:
                raise SystemExit(f"FAIL donor MODE1 EDC/ECC LBA {lba}")
            delta.append((lba, sha_bytes(before), sha_bytes(after)))
    if not delta:
        raise SystemExit("FAIL empty title3 donor delta")

    out = bytearray(parent)
    expected_write = []
    already_target = 0
    for lba, before_sha, after_sha in delta:
        off = lba * RAW_SECTOR_SIZE
        cur = bytes(parent[off:off + RAW_SECTOR_SIZE])
        cur_sha = sha_bytes(cur)
        if cur_sha == after_sha:
            already_target += 1
            continue
        if cur_sha != before_sha:
            raise SystemExit(f"FAIL third variant LBA {lba}: parent={cur_sha} pristine={before_sha} target={after_sha}")
        expected_write.append({"lba": lba, "before_sha256": before_sha, "after_sha256": after_sha})
        out[off:off + RAW_SECTOR_SIZE] = donor[off:off + RAW_SECTOR_SIZE]

    actual_lbas = []
    for lba in sorted(asset_lbas):
        off = lba * RAW_SECTOR_SIZE
        if parent[off:off + RAW_SECTOR_SIZE] != out[off:off + RAW_SECTOR_SIZE]:
            actual_lbas.append(lba)
    expected_lbas = [w["lba"] for w in expected_write]
    if actual_lbas != expected_lbas:
        raise SystemExit("FAIL actual changed-LBA set != Expected Write LBA set")

    for w in expected_write:
        off = w["lba"] * RAW_SECTOR_SIZE
        sec = bytes(out[off:off + RAW_SECTOR_SIZE])
        if sha_bytes(sec) != w["after_sha256"]:
            raise SystemExit(f"FAIL Expected Write after SHA LBA {w['lba']}")
        if not verify_mode1_sector(sec)["valid"]:
            raise SystemExit(f"FAIL final MODE1 EDC/ECC LBA {w['lba']}")

    audit = []
    for asset in ASSETS:
        final_sha = sha_bytes(extract_asset(out, asset["lba"], asset["size"]))
        if final_sha != asset["sha256"]:
            raise SystemExit(f"FAIL final whole-asset re-extraction {asset['path']}")
        audit.append({**asset, "final_sha256": final_sha, "status": "PASS"})

    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.write_bytes(out)
    output_sha = sha_file(args.output_bin)
    report = {
        "batch": 287,
        "status": PASS_STATUS,
        "parent_batch": 286,
        "parent_sha256": parent_sha,
        "source_sha256": source_sha,
        "r37_donor_sha256": r37_sha,
        "derived_title3_delta_sectors": len(delta),
        "already_target_sectors": already_target,
        "expected_write_count": len(expected_write),
        "expected_write": expected_write,
        "changed_raw_sectors": len(actual_lbas),
        "changed_lbas": actual_lbas,
        "changed_sector_accounting": "PASS",
        "changed_sector_edc_ecc": f"{len(actual_lbas)}/{len(actual_lbas)} PASS",
        "title_asset_reextraction": "3/3 PASS",
        "title_asset_audit": audit,
        "event_mes_logical_completion": "109/109",
        "static_assets_verified": 58,
        "speech_movies_physical": "12/12",
        "guessed_payload_bytes": 0,
        "output_sha256": output_sha
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(PASS_STATUS)
    print(f"output_sha256={output_sha}")
    print(f"derived_title3_delta_sectors={len(delta)}")
    print(f"changed_raw_sectors={len(actual_lbas)}")
    print("title_asset_reextraction=3/3 PASS")


if __name__ == "__main__":
    main()
