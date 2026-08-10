#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RAW = 2352
SYNC = bytes([0] + [0xFF] * 10 + [0])
B269_STATUS = "PASS_B247_STATIC58_PLUS_DEDUP_MASS137_EVENT34_EXECUTABLE_CANDIDATE"
B271_STATUS = "PASS_BATCH269_PLUS_B64_MOVIE2_EXECUTABLE_CANDIDATE"
B272_STATUS = "PASS_BATCH269_PLUS_R37_MOVIE6_EXECUTABLE_CANDIDATE"


def shaf(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def shab(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _edc_lut() -> list[int]:
    out = []
    for i in range(256):
        v = i
        for _ in range(8):
            v = (v >> 1) ^ (0xD8018001 if v & 1 else 0)
        out.append(v & 0xFFFFFFFF)
    return out


EDC = _edc_lut()


def edc(data: bytes) -> int:
    v = 0
    for x in data:
        v = (v >> 8) ^ EDC[(v ^ x) & 0xFF]
    return v & 0xFFFFFFFF


def _ecc_luts() -> tuple[list[int], list[int]]:
    fwd = [0] * 256
    back = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        fwd[i] = j & 0xFF
        back[i ^ fwd[i]] = i
    return fwd, back


EF, EB = _ecc_luts()


def ecc(src: bytes, major: int, minor: int, mult: int, inc: int) -> bytes:
    size = major * minor
    out = bytearray(major * 2)
    for m in range(major):
        idx = (m >> 1) * mult + (m & 1)
        a = b = 0
        for _ in range(minor):
            t = src[idx]
            idx = (idx + inc) % size
            a ^= t
            b ^= t
            a = EF[a]
        a = EB[EF[a] ^ b]
        out[m] = a
        out[m + major] = a ^ b
    return bytes(out)


def verify_mode1(sec: bytes) -> bool:
    return (
        len(sec) == RAW
        and sec[:12] == SYNC
        and sec[15] == 1
        and int.from_bytes(sec[0x810:0x814], "little") == edc(sec[:0x810])
        and sec[0x814:0x81C] == bytes(8)
        and sec[0x81C:0x8C8] == ecc(sec[0x0C:0x81C], 86, 24, 2, 86)
        and sec[0x8C8:0x930] == ecc(sec[0x0C:0x8C8], 52, 43, 86, 88)
    )


def sector_delta(parent: Path, child: Path) -> dict[int, bytes]:
    if parent.stat().st_size != child.stat().st_size:
        raise SystemExit("component size mismatch")
    out: dict[int, bytes] = {}
    with parent.open("rb") as p, child.open("rb") as c:
        lba = 0
        while True:
            ps = p.read(RAW)
            cs = c.read(RAW)
            if not ps and not cs:
                break
            if len(ps) != RAW or len(cs) != RAW:
                raise SystemExit("partial raw sector at EOF")
            if ps != cs:
                out[lba] = cs
            lba += 1
    return out


def extract_asset(raw: Path, lba: int, size: int) -> bytes:
    out = bytearray()
    remain = size
    cur = lba
    with raw.open("rb") as f:
        while remain:
            take = min(2048, remain)
            f.seek(cur * RAW + 16)
            chunk = f.read(take)
            if len(chunk) != take:
                raise SystemExit("short asset re-extraction")
            out.extend(chunk)
            remain -= take
            cur += 1
    return bytes(out)


def load_result(path: Path, status: str) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("status") != status:
        raise SystemExit(f"result status mismatch: {path}")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch273: merge Batch271 and Batch272 sector deltas over exact common Batch269")
    ap.add_argument("--batch269", type=Path, required=True)
    ap.add_argument("--batch269-result", type=Path, required=True)
    ap.add_argument("--batch271", type=Path, required=True)
    ap.add_argument("--batch271-result", type=Path, required=True)
    ap.add_argument("--batch272", type=Path, required=True)
    ap.add_argument("--batch272-result", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, default=Path("manifests/CD1_BATCH273_MOVIE12_PHYSICAL_UNION.json"))
    ap.add_argument("--output", type=Path, default=Path("Sakura_Taisen_2_Disc1_B273_Movie12_Union_KO.bin"))
    ap.add_argument("--result", type=Path, default=Path("BATCH273_RESULT.json"))
    a = ap.parse_args()

    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    if manifest.get("format") != "ST2-CD1-BATCH273-MOVIE12-PHYSICAL-UNION-v1":
        raise SystemExit("manifest format mismatch")

    r269 = load_result(a.batch269_result, B269_STATUS)
    r271 = load_result(a.batch271_result, B271_STATUS)
    r272 = load_result(a.batch272_result, B272_STATUS)
    parent_sha = shaf(a.batch269)
    if parent_sha != r269.get("output_sha256"):
        raise SystemExit("Batch269 output SHA mismatch")
    if r271.get("parent_sha256") != parent_sha or r272.get("parent_sha256") != parent_sha:
        raise SystemExit("component parent lineage mismatch")
    if shaf(a.batch271) != r271.get("output_sha256"):
        raise SystemExit("Batch271 output SHA mismatch")
    if shaf(a.batch272) != r272.get("output_sha256"):
        raise SystemExit("Batch272 output SHA mismatch")
    if r271.get("whole_asset_reextraction") != "2/2 PASS":
        raise SystemExit("Batch271 whole-asset gate missing")
    if r272.get("whole_asset_reextraction") != "6/6 PASS":
        raise SystemExit("Batch272 whole-asset gate missing")

    d271 = sector_delta(a.batch269, a.batch271)
    d272 = sector_delta(a.batch269, a.batch272)
    overlaps = sorted(set(d271) & set(d272))
    nonidentical = [lba for lba in overlaps if d271[lba] != d272[lba]]
    if nonidentical:
        raise SystemExit(f"non-identical component sector overlap: {nonidentical[:8]}")

    union = dict(d271)
    union.update(d272)
    shutil.copyfile(a.batch269, a.output)
    expected = []
    with a.output.open("r+b") as f:
        for lba in sorted(union):
            f.seek(lba * RAW)
            before = f.read(RAW)
            after = union[lba]
            expected.append({
                "lba": lba,
                "before_sha256": shab(before),
                "after_sha256": shab(after),
            })
            f.seek(lba * RAW)
            f.write(after)

    expected_bad = []
    ecc_bad = []
    with a.output.open("rb") as f:
        for rec in expected:
            f.seek(rec["lba"] * RAW)
            sec = f.read(RAW)
            if shab(sec) != rec["after_sha256"]:
                expected_bad.append(rec["lba"])
            if not verify_mode1(sec):
                ecc_bad.append(rec["lba"])
    if expected_bad:
        raise SystemExit(f"Expected Write failures: {expected_bad[:8]}")
    if ecc_bad:
        raise SystemExit(f"changed-sector EDC/ECC failures: {ecc_bad[:8]}")
    if len(expected) != len(union):
        raise SystemExit("changed-sector accounting mismatch")

    assets = []
    for result in (r271, r272):
        for item in result.get("assets", []):
            key = (item["iso_path"], item["replacement_sha256"])
            if key not in {(x["iso_path"], x["replacement_sha256"]) for x in assets}:
                assets.append(item)
    if len(assets) != 8:
        raise SystemExit(f"promoted asset union expected 8 unique assets, got {len(assets)}")

    reextract = []
    for item in assets:
        got = shab(extract_asset(a.output, int(item["lba"]), int(item["size"])))
        ok = got == item["replacement_sha256"]
        reextract.append({"iso_path": item["iso_path"], "sha256": got, "pass": ok})
        if not ok:
            raise SystemExit(f"final whole-asset re-extraction failed: {item['iso_path']}")

    result = {
        "batch": 273,
        "status": "PASS_BATCH269_PLUS_ALL_12_SPEECH_MOVIES_PHYSICAL_UNION",
        "parent_batch": 269,
        "parent_sha256": parent_sha,
        "component_batches": [271, 272],
        "component_changed_sectors": {"271": len(d271), "272": len(d272)},
        "component_overlap_sectors": len(overlaps),
        "component_nonidentical_overlaps": 0,
        "union_changed_sector_count": len(union),
        "expected_write_records": len(expected),
        "expected_write": f"{len(expected)}/{len(expected)} PASS",
        "changed_sector_edc_ecc": f"{len(union)}/{len(union)} PASS",
        "changed_sector_accounting": "PASS",
        "newly_promoted_assets_over_batch269": 8,
        "speech_movie_candidates_in_final_union": "12/12",
        "episode_title_cards_inherited_from_batch269": "6/6",
        "final_promoted_asset_reextraction": "8/8 PASS",
        "reextraction": reextract,
        "output_sha256": shaf(a.output),
        "guessed_payload_bytes": False,
    }
    a.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
