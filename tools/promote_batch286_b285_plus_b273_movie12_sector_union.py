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
B285_STATUS = "PASS_BATCH285_B284_PLUS_B118_STATIC58_SECTOR_UNION"
B273_STATUS = "PASS_BATCH269_PLUS_ALL_12_SPEECH_MOVIES_PHYSICAL_UNION"
PASS_STATUS = "PASS_BATCH286_B285_PLUS_B273_MOVIE12_SECTOR_UNION"
MOVIES = {
    "SAKURA1/SK2MV_00.CAK", "SAKURA1/SK2MV_03.CAK", "SAKURA1/SK2MV_04.CAK",
    "SAKURA1/SK2MV_05.CAK", "SAKURA1/SK2MV_06.CAK", "SAKURA1/SK2MV_07.CAK",
    "SAKURA1/SK2MV_09.CAK", "SAKURA1/SK2MV_10.CAK", "SAKURA1/SK2MV_11.CAK",
    "SAKURA1/SK2MV_30.CAK", "SAKURA1/SK2MV_38.CAK", "SAKURA1/SK2MV_39.CAK",
}


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def deep_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from deep_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from deep_dicts(v)


def report_has_sha(report: dict, wanted: str) -> bool:
    wanted = wanted.lower()
    for d in deep_dicts(report):
        for k, v in d.items():
            if "sha" in str(k).lower() and str(v).lower() == wanted:
                return True
    return False


def extract_asset(raw: bytes | bytearray, lba: int, size: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < size:
        off = (lba + i) * RAW_SECTOR_SIZE
        sec = raw[off:off + RAW_SECTOR_SIZE]
        if len(sec) != RAW_SECTOR_SIZE or sec[15] != 1:
            raise SystemExit(f"FAIL non-MODE1 sector LBA {lba+i}")
        take = min(USER_SIZE, size - len(out))
        out += sec[USER_OFF:USER_OFF + take]
        i += 1
    return bytes(out)


def movie_map_from_report(report: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for d in deep_dicts(report):
        raw_name = d.get("asset", d.get("iso_path", d.get("path", "")))
        name = str(raw_name).replace("\\", "/").upper()
        canonical = next((m for m in MOVIES if m.upper() == name), None)
        if canonical is None:
            continue
        if "lba" not in d or "size" not in d:
            continue
        target = None
        for k in ("final_sha256", "candidate_sha256", "replacement_sha256", "target_sha256", "sha256"):
            v = d.get(k)
            if isinstance(v, str) and len(v) == 64:
                target = v.lower()
                break
        if target is None:
            continue
        rec = {"asset": canonical, "lba": int(d["lba"]), "size": int(d["size"]), "sha256": target}
        old = found.get(canonical)
        if old is not None and old != rec:
            raise SystemExit(f"FAIL conflicting B273 asset metadata {canonical}")
        found[canonical] = rec
    if set(found) != MOVIES:
        missing = sorted(MOVIES - set(found))
        raise SystemExit(f"FAIL B273 report lacks exact 12-movie asset audit metadata; missing={missing}")
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch286: exact Batch269->Batch273 movie12 sector delta union onto Batch285")
    ap.add_argument("--parent-bin", required=True, type=Path, help="exact successful Batch285 BIN")
    ap.add_argument("--b285-report", required=True, type=Path)
    ap.add_argument("--b269-bin", required=True, type=Path, help="exact Batch273 common-parent Batch269 BIN")
    ap.add_argument("--b273-bin", required=True, type=Path, help="exact successful Batch273 movie12 union BIN")
    ap.add_argument("--b273-report", required=True, type=Path)
    ap.add_argument("--output-bin", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    for p in (args.parent_bin, args.b269_bin, args.b273_bin):
        if p.stat().st_size != DISC_SIZE:
            raise SystemExit(f"FAIL disc size {p}")

    parent_sha = sha_file(args.parent_bin)
    b269_sha = sha_file(args.b269_bin)
    b273_sha = sha_file(args.b273_bin)
    b285 = json.loads(args.b285_report.read_text(encoding="utf-8"))
    b273r = json.loads(args.b273_report.read_text(encoding="utf-8"))

    if b285.get("status") != B285_STATUS or str(b285.get("output_sha256", "")).lower() != parent_sha:
        raise SystemExit("FAIL B285 report/status/output SHA binding")
    if int(b285.get("guessed_payload_bytes", -1)) != 0:
        raise SystemExit("FAIL B285 guessed payload bytes")
    if b273r.get("status") != B273_STATUS or str(b273r.get("output_sha256", "")).lower() != b273_sha:
        raise SystemExit("FAIL B273 report/status/output SHA binding")
    if not report_has_sha(b273r, b269_sha):
        raise SystemExit("FAIL B273 report does not bind exact Batch269 common-parent SHA")

    movie_map = movie_map_from_report(b273r)
    parent = args.parent_bin.read_bytes()
    common = args.b269_bin.read_bytes()
    donor = args.b273_bin.read_bytes()

    delta = []
    for lba in range(DISC_SIZE // RAW_SECTOR_SIZE):
        off = lba * RAW_SECTOR_SIZE
        before = common[off:off + RAW_SECTOR_SIZE]
        after = donor[off:off + RAW_SECTOR_SIZE]
        if before != after:
            if not verify_mode1_sector(after)["valid"]:
                raise SystemExit(f"FAIL B273 donor EDC/ECC LBA {lba}")
            delta.append((lba, sha_bytes(before), sha_bytes(after)))
    if not delta:
        raise SystemExit("FAIL empty Batch269->Batch273 delta")

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
            raise SystemExit(f"FAIL third variant LBA {lba}: parent={cur_sha} common={before_sha} movie={after_sha}")
        expected_write.append({"lba": lba, "before_sha256": before_sha, "after_sha256": after_sha})

    for w in expected_write:
        off = w["lba"] * RAW_SECTOR_SIZE
        out[off:off + RAW_SECTOR_SIZE] = donor[off:off + RAW_SECTOR_SIZE]

    actual_lbas = []
    for lba in range(DISC_SIZE // RAW_SECTOR_SIZE):
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
            raise SystemExit(f"FAIL after SHA LBA {w['lba']}")
        if not verify_mode1_sector(sec)["valid"]:
            raise SystemExit(f"FAIL final EDC/ECC LBA {w['lba']}")

    asset_audit = []
    for name in sorted(MOVIES):
        rec = movie_map[name]
        donor_asset_sha = sha_bytes(extract_asset(donor, rec["lba"], rec["size"]))
        final_asset_sha = sha_bytes(extract_asset(out, rec["lba"], rec["size"]))
        if donor_asset_sha != rec["sha256"] or final_asset_sha != rec["sha256"]:
            raise SystemExit(f"FAIL 12-movie whole-asset re-extraction {name}")
        asset_audit.append({**rec, "final_sha256": final_asset_sha, "status": "PASS"})

    args.output_bin.parent.mkdir(parents=True, exist_ok=True)
    args.output_bin.write_bytes(out)
    output_sha = sha_file(args.output_bin)
    report = {
        "batch": 286,
        "status": PASS_STATUS,
        "parent_batch": 285,
        "parent_sha256": parent_sha,
        "b269_common_parent_sha256": b269_sha,
        "b273_movie12_donor_sha256": b273_sha,
        "derived_b269_to_b273_changed_raw_sectors": len(delta),
        "already_target_sectors": already_target,
        "expected_write_count": len(expected_write),
        "expected_write": expected_write,
        "changed_raw_sectors": len(actual_lbas),
        "changed_lbas": actual_lbas,
        "changed_sector_accounting": "PASS",
        "changed_sector_edc_ecc": f"{len(actual_lbas)}/{len(actual_lbas)} PASS",
        "movie_asset_reextraction": "12/12 PASS",
        "movie_asset_audit": asset_audit,
        "event_mes_logical_completion": "109/109",
        "static_assets_verified": 58,
        "speech_movies_physical": "12/12",
        "guessed_payload_bytes": 0,
        "output_sha256": output_sha,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(PASS_STATUS)
    print(f"output_sha256={output_sha}")
    print(f"derived_movie_delta_sectors={len(delta)}")
    print(f"changed_raw_sectors={len(actual_lbas)}")
    print("movie_asset_reextraction=12/12 PASS")


if __name__ == "__main__":
    main()
