#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RAW = 2352
USER = 2048
UOFF = 16
SYNC = bytes([0] + [0xFF] * 10 + [0])
R37_SHA = "56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736"
B269_STATUS = "PASS_B247_STATIC58_PLUS_DEDUP_MASS137_EVENT34_EXECUTABLE_CANDIDATE"


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


def rebuild_mode1(sec: bytearray) -> None:
    if len(sec) != RAW or sec[:12] != SYNC or sec[15] != 1:
        raise SystemExit("target footprint contains a non-MODE1 sector")
    sec[0x810:0x814] = edc(sec[:0x810]).to_bytes(4, "little")
    sec[0x814:0x81C] = bytes(8)
    sec[0x81C:0x8C8] = ecc(sec[0x0C:0x81C], 86, 24, 2, 86)
    sec[0x8C8:0x930] = ecc(sec[0x0C:0x8C8], 52, 43, 86, 88)


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


def extract_asset(raw: Path, lba: int, size: int) -> bytes:
    out = bytearray()
    remain = size
    cur = lba
    with raw.open("rb") as f:
        while remain:
            take = min(USER, remain)
            f.seek(cur * RAW + UOFF)
            chunk = f.read(take)
            if len(chunk) != take:
                raise SystemExit("short asset extraction")
            out.extend(chunk)
            remain -= take
            cur += 1
    return bytes(out)


def overlay_asset(f, payload: bytes, lba: int, expected: list[dict]) -> set[int]:
    remain = len(payload)
    pos = 0
    cur = lba
    changed: set[int] = set()
    while remain:
        take = min(USER, remain)
        f.seek(cur * RAW)
        old = f.read(RAW)
        if len(old) != RAW:
            raise SystemExit("short target sector")
        sec = bytearray(old)
        sec[UOFF:UOFF + take] = payload[pos:pos + take]
        if sec != old:
            rebuild_mode1(sec)
            new = bytes(sec)
            expected.append({
                "lba": cur,
                "before_sha256": shab(old),
                "after_sha256": shab(new),
            })
            f.seek(cur * RAW)
            f.write(new)
            changed.add(cur)
        pos += take
        remain -= take
        cur += 1
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Batch272: recover six exact subtitle CAKs from ST2R37 and promote them onto Batch269"
    )
    ap.add_argument("--r37", type=Path, required=True)
    ap.add_argument("--batch269", type=Path, required=True)
    ap.add_argument("--batch269-result", type=Path, required=True)
    ap.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifests/CD1_BATCH272_R37_MOVIE6_PROMOTION.json"),
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("Sakura_Taisen_2_Disc1_B272_R37_Movie6_KO.bin"),
    )
    ap.add_argument("--result", type=Path, default=Path("BATCH272_RESULT.json"))
    a = ap.parse_args()

    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    if manifest.get("format") != "ST2-CD1-BATCH272-R37-MOVIE6-PROMOTION-v1":
        raise SystemExit("manifest format mismatch")
    if manifest.get("guessed_payload_bytes") is not False:
        raise SystemExit("guessed-byte policy mismatch")
    if len(manifest.get("replacement_files", [])) != 6:
        raise SystemExit("Batch272 requires exactly six assets")
    if shaf(a.r37) != R37_SHA:
        raise SystemExit("ST2R37 exact whole-disc SHA mismatch")

    parent_result = json.loads(a.batch269_result.read_text(encoding="utf-8"))
    if parent_result.get("status") != B269_STATUS:
        raise SystemExit("Batch269 status mismatch")
    parent_sha = shaf(a.batch269)
    if parent_sha != parent_result.get("output_sha256"):
        raise SystemExit("Batch269 output SHA mismatch")

    payloads: list[tuple[dict, bytes]] = []
    for item in manifest["replacement_files"]:
        payload = extract_asset(a.r37, int(item["lba"]), int(item["size"]))
        got = shab(payload)
        if got != item["replacement_sha256"]:
            raise SystemExit(f"R37 asset SHA mismatch: {item['iso_path']}")
        payloads.append((item, payload))

    shutil.copyfile(a.batch269, a.output)
    expected: list[dict] = []
    changed: set[int] = set()
    per_asset = []
    with a.output.open("r+b") as f:
        for item, payload in payloads:
            asset_changed = overlay_asset(f, payload, int(item["lba"]), expected)
            changed |= asset_changed
            per_asset.append({
                "iso_path": item["iso_path"],
                "changed_sector_count": len(asset_changed),
            })

    expected_bad = []
    ecc_bad = []
    with a.output.open("rb") as f:
        for record in expected:
            f.seek(record["lba"] * RAW)
            sec = f.read(RAW)
            if shab(sec) != record["after_sha256"]:
                expected_bad.append(record["lba"])
            if not verify_mode1(sec):
                ecc_bad.append(record["lba"])
    if expected_bad:
        raise SystemExit(f"Expected Write failures: {expected_bad[:8]}")
    if ecc_bad:
        raise SystemExit(f"changed-sector EDC/ECC failures: {ecc_bad[:8]}")
    if len(expected) != len(changed):
        raise SystemExit("changed-sector accounting mismatch")

    reextraction = []
    for item, _ in payloads:
        got = shab(extract_asset(a.output, int(item["lba"]), int(item["size"])))
        ok = got == item["replacement_sha256"]
        reextraction.append({
            "iso_path": item["iso_path"],
            "sha256": got,
            "pass": ok,
        })
        if not ok:
            raise SystemExit(f"whole-asset re-extraction failed: {item['iso_path']}")

    result = {
        "batch": 272,
        "status": "PASS_BATCH269_PLUS_R37_MOVIE6_EXECUTABLE_CANDIDATE",
        "parent_batch": 269,
        "parent_sha256": parent_sha,
        "recovery_disc": "ST2R37",
        "recovery_disc_sha256": R37_SHA,
        "new_unique_assets": 6,
        "assets": [
            {
                "iso_path": item["iso_path"],
                "lba": item["lba"],
                "size": item["size"],
                "replacement_sha256": item["replacement_sha256"],
            }
            for item, _ in payloads
        ],
        "per_asset": per_asset,
        "changed_sector_count": len(changed),
        "expected_write_records": len(expected),
        "expected_write": f"{len(expected)}/{len(expected)} PASS",
        "changed_sector_edc_ecc": f"{len(changed)}/{len(changed)} PASS",
        "changed_sector_accounting": "PASS",
        "whole_asset_reextraction": "6/6 PASS",
        "reextraction": reextraction,
        "output_sha256": shaf(a.output),
        "guessed_payload_bytes": False,
    }
    a.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
