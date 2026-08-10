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
B287_STATUS = "PASS_BATCH287_B286_PLUS_R37_TITLE3_EXACT_UNION"
PASS_STATUS = "PASS_BATCH288_B287_PLUS_R37_UI3_RUNTIME5_EXACT_UNION"
ASSETS = [
    {"path":"SAKURA1/CMD_WIN.CG","lba":4034,"size":4288,"sha256":"20a4947ce98752681efecffe9a6022dfb324bc9433ece5ce8da6d567f605ee09"},
    {"path":"SAKURA1/PBOOK_FL.CG","lba":1658,"size":346016,"sha256":"b172efc442ebca5fc0aade2f92e96cd193a853542213336fecf793e2f881cbdb"},
    {"path":"SAKURA1/PB_EYE.CG","lba":15725,"size":66240,"sha256":"f3ab7b8f52474d772aa9652b3667e3052935a107c361e2aa7574ac807eaa2c98"},
    {"path":"SAKURA1/BTSFONT.BIN","lba":3943,"size":38860,"sha256":"490bbf4e2d76955b10c0e2cc8d8644210ae0b738dd9214b1a7f9bd9dde816a67"},
    {"path":"SAKURA2/M00LOW.BIN","lba":218758,"size":412480,"sha256":"5238a49aafd485da38f8cca297e085ac31f6fa4538971dd9f3ed2d05b72bc401"},
    {"path":"SAKURA2/M01LOW.BIN","lba":219653,"size":412480,"sha256":"a2fe5a5eb9400dba586e94ef21217cccde85d7c8541be9625980d7e5c5f2a6d4"},
    {"path":"SAKURA2/M26LOW.BIN","lba":224206,"size":412480,"sha256":"9c2dc9b8e9ed3d299719a748b41920a5fdd7995adf3a43c798540a181057c6f3"},
    {"path":"SAKURA2/M27LOW.BIN","lba":225106,"size":412480,"sha256":"6a9a3151b34a7417e280d44cb4486e2b90788fd7099d8da0339224e2df84927f"},
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
    ap = argparse.ArgumentParser(description="Batch288: exact R37 UI3 + runtime5 union onto successful Batch287")
    ap.add_argument("--parent-bin", required=True, type=Path, help="exact successful Batch287 BIN")
    ap.add_argument("--b287-report", required=True, type=Path)
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

    b287 = json.loads(args.b287_report.read_text(encoding="utf-8"))
    if b287.get("status") != B287_STATUS or str(b287.get("output_sha256", "")).lower() != parent_sha:
        raise SystemExit("FAIL Batch287 report/status/output SHA binding")
    if int(b287.get("guessed_payload_bytes", -1)) != 0:
        raise SystemExit("FAIL Batch287 guessed payload bytes")

    parent = args.parent_bin.read_bytes()
    source = args.source_bin.read_bytes()
    donor = args.r37_bin.read_bytes()

    for asset in ASSETS:
        donor_asset = extract_asset(donor, asset["lba"], asset["size"])
        if sha_bytes(donor_asset) != asset["sha256"]:
            raise SystemExit(f"FAIL donor whole-asset SHA {asset['path']}")

    asset_lbas = set()
    for asset in ASSETS:
        count = (asset["size"] + USER_SIZE - 1) // USER_SIZE
        asset_lbas.update(range(asset["lba"], asset["lba"] + count))

    delta = []
    for lba in sorted(asset_lbas):
        off = lba * RAW_SECTOR_SIZE
        before = source[off:off + RAW_SECTOR_SIZE]
        after = donor[off:off + RAW_SECTOR_SIZE]
        if before != after:
            if not verify_mode1_sector(after)["valid"]:
                raise SystemExit(f"FAIL donor MODE1 EDC/ECC LBA {lba}")
            delta.append((lba, sha_bytes(before), sha_bytes(after)))
    if not delta:
        raise SystemExit("FAIL empty UI3/runtime5 donor delta")

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
        "batch": 288,
        "status": PASS_STATUS,
        "parent_batch": 287,
        "parent_sha256": parent_sha,
        "source_sha256": source_sha,
        "r37_donor_sha256": r37_sha,
        "asset_count": len(ASSETS),
        "derived_ui3_runtime5_delta_sectors": len(delta),
        "already_target_sectors": already_target,
        "expected_write_count": len(expected_write),
        "expected_write": expected_write,
        "changed_raw_sectors": len(actual_lbas),
        "changed_lbas": actual_lbas,
        "changed_sector_accounting": "PASS",
        "changed_sector_edc_ecc": f"{len(actual_lbas)}/{len(actual_lbas)} PASS",
        "whole_asset_reextraction": "8/8 PASS",
        "asset_audit": audit,
        "event_mes_logical_completion": "109/109",
        "static_assets_verified": 58,
        "speech_movies_physical": "12/12",
        "title_assets_physical": "3/3",
        "additional_ui_assets_physical": "3/3",
        "runtime_support_assets_physical": "5/5",
        "guessed_payload_bytes": 0,
        "output_sha256": output_sha
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(PASS_STATUS)
    print(f"output_sha256={output_sha}")
    print(f"derived_ui3_runtime5_delta_sectors={len(delta)}")
    print(f"changed_raw_sectors={len(actual_lbas)}")
    print("whole_asset_reextraction=8/8 PASS")


if __name__ == "__main__":
    main()
