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
PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
DONOR_SHA = "75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20"
HERE = Path(__file__).resolve().parent
DEFAULT_B200 = HERE.parent / "manifests" / "BATCH200_REAL_FULL58_RECOVERY.json"


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
    sector = 0
    while len(out) < size:
        off = (lba + sector) * RAW_SECTOR_SIZE
        sec = raw[off:off + RAW_SECTOR_SIZE]
        if len(sec) != RAW_SECTOR_SIZE or sec[15] != 1:
            raise ValueError(f"not MODE1/2352 at LBA {lba + sector}")
        take = min(USER_SIZE, size - len(out))
        out += sec[USER_OFF:USER_OFF + take]
        sector += 1
    return bytes(out)


def rebuild_mode1(sec: bytearray) -> None:
    sec[0x810:0x814] = edc(bytes(sec[:0x810])).to_bytes(4, "little")
    sec[0x814:0x81C] = bytes(8)
    sec[0x81C:0x8C8] = _ecc_compute(bytes(sec[0x0C:0x81C]), 86, 24, 2, 86)
    sec[0x8C8:0x930] = _ecc_compute(bytes(sec[0x0C:0x8C8]), 52, 43, 86, 88)


def write_asset(raw: bytearray, lba: int, payload: bytes, writes: dict[int, dict]) -> None:
    cursor = 0
    idx = 0
    while cursor < len(payload):
        cur_lba = lba + idx
        off = cur_lba * RAW_SECTOR_SIZE
        before = bytes(raw[off:off + RAW_SECTOR_SIZE])
        if not verify_mode1_sector(before)["valid"]:
            raise ValueError(f"parent EDC/ECC invalid at LBA {cur_lba}")
        sec = bytearray(before)
        take = min(USER_SIZE, len(payload) - cursor)
        sec[USER_OFF:USER_OFF + take] = payload[cursor:cursor + take]
        rebuild_mode1(sec)
        after = bytes(sec)
        if before != after:
            if not verify_mode1_sector(after)["valid"]:
                raise ValueError(f"rebuilt EDC/ECC invalid at LBA {cur_lba}")
            prev = writes.get(cur_lba)
            rec = {"lba": cur_lba, "before_sha256": sha_bytes(before), "after_sha256": sha_bytes(after)}
            if prev and prev["after_sha256"] != rec["after_sha256"]:
                raise ValueError(f"conflicting Expected Write at LBA {cur_lba}")
            raw[off:off + RAW_SECTOR_SIZE] = after
            writes[cur_lba] = rec
        cursor += take
        idx += 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Physically reunite exact B118/B200 static58 assets into the latest Disc1 cumulative parent")
    ap.add_argument("--pristine-bin", required=True, type=Path)
    ap.add_argument("--donor-bin", required=True, type=Path, help="Exact B118/B200 full58 verified disc")
    ap.add_argument("--parent-bin", required=True, type=Path)
    ap.add_argument("--parent-sha256", required=True)
    ap.add_argument("--b200-manifest", type=Path, default=DEFAULT_B200)
    ap.add_argument("--output-bin", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    for p in (args.pristine_bin, args.donor_bin, args.parent_bin):
        if p.stat().st_size != DISC_SIZE:
            raise SystemExit(f"FAIL disc size: {p}")
    if sha_file(args.pristine_bin) != PRISTINE_SHA:
        raise SystemExit("FAIL pristine SHA-256")
    if sha_file(args.donor_bin) != DONOR_SHA:
        raise SystemExit("FAIL donor B118/B200 SHA-256")
    parent_sha = sha_file(args.parent_bin)
    if parent_sha.lower() != args.parent_sha256.lower():
        raise SystemExit(f"FAIL parent SHA expected={args.parent_sha256} actual={parent_sha}")

    m = json.loads(args.b200_manifest.read_text(encoding="utf-8"))
    if m.get("status") != "PASS_REAL_FULL58_EXACT_RECOVERY" or len(m.get("assets", [])) != 58:
        raise SystemExit("FAIL B200 manifest trust gate")
    if m.get("output_disc_sha256") != DONOR_SHA or m.get("reextraction") != "58/58 PASS":
        raise SystemExit("FAIL B200 donor lineage")

    pristine = args.pristine_bin.read_bytes()
    donor = args.donor_bin.read_bytes()
    out = bytearray(args.parent_bin.read_bytes())
    writes: dict[int, dict] = {}
    audit = []

    for a in m["assets"]:
        name, lba, size, target_sha = a["name"], int(a["lba"]), int(a["size"]), a["sha256"]
        src = extract_asset(pristine, lba, size)
        target = extract_asset(donor, lba, size)
        current = extract_asset(out, lba, size)
        src_sha, target_actual, current_sha = sha_bytes(src), sha_bytes(target), sha_bytes(current)
        if target_actual != target_sha:
            raise SystemExit(f"FAIL donor asset {name} expected={target_sha} actual={target_actual}")
        if current_sha not in {src_sha, target_sha}:
            raise SystemExit(f"FAIL third variant {name}: {current_sha}")
        state = "already_target" if current_sha == target_sha else "promoted_from_pristine"
        if current_sha == src_sha and src_sha != target_sha:
            write_asset(out, lba, target, writes)
        final_sha = sha_bytes(extract_asset(out, lba, size))
        if final_sha != target_sha:
            raise SystemExit(f"FAIL whole-asset re-extraction {name}")
        audit.append({"asset": name, "lba": lba, "size": size, "pristine_sha256": src_sha,
                      "target_sha256": target_sha, "before_sha256": current_sha,
                      "after_sha256": final_sha, "state": state, "reextraction": "PASS"})

    changed_lbas = sorted(writes)
    for lba in changed_lbas:
        off = lba * RAW_SECTOR_SIZE
        if not verify_mode1_sector(bytes(out[off:off + RAW_SECTOR_SIZE]))["valid"]:
            raise SystemExit(f"FAIL final changed-sector EDC/ECC LBA {lba}")

    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.write_bytes(out)
    output_sha = sha_file(args.output_bin)
    report = {
        "batch": 282,
        "status": "PASS_BATCH282_STATIC58_PHYSICAL_REUNION",
        "pristine_sha256": PRISTINE_SHA,
        "donor_sha256": DONOR_SHA,
        "parent_sha256": parent_sha,
        "output_sha256": output_sha,
        "guessed_payload_bytes": 0,
        "assets": 58,
        "asset_reextraction": "58/58 PASS",
        "asset_audit": audit,
        "expected_write": [writes[x] for x in changed_lbas],
        "changed_raw_sectors": len(changed_lbas),
        "changed_lbas": changed_lbas,
        "changed_sector_accounting": "PASS",
        "changed_sector_edc_ecc": f"{len(changed_lbas)}/{len(changed_lbas)} PASS",
        "non_target_parent_sectors_policy": "preserved",
        "cumulative_scope": {"story": "141/141", "battle_static": "58/58 physical", "movie_inventory": "24/24 logical"}
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    print(f"output_sha256={output_sha}")
    print(f"changed_raw_sectors={len(changed_lbas)}")
    print("static_assets=58/58 physical")


if __name__ == "__main__":
    main()
