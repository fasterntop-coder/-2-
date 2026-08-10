#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

RAW = 2352
USER = 2048
SYNC = bytes([0] + [0xFF] * 10 + [0])
PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PARENT_STATUS = "PASS_BATCH269_PLUS_ALL_12_SPEECH_MOVIES_PHYSICAL_UNION"
SUCCESS_STATUS = "PASS_BATCH273_PLUS_EVENT109_COMPLETE_EXECUTABLE_CANDIDATE"

SPECS = {
    50: ("ST2-R41-batch50-replacement-manifest-v1", 6),
    51: ("ST2-R41-batch51-replacement-manifest-v1", 9),
    52: ("ST2-R41-batch52-replacement-manifest-v1", 18),
    53: ("ST2-R41-batch53-replacement-manifest-v1", 19),
    54: ("ST2-R41-batch54-replacement-manifest-v1", 8),
    55: ("ST2-R41-batch55-final-replacement-manifest-v1", 15),
}


def shab(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shaf(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


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


def rebuild_mode1(sec: bytes) -> bytes:
    if len(sec) != RAW or sec[:12] != SYNC or sec[15] != 1:
        raise SystemExit("target sector is not MODE1/2352")
    b = bytearray(sec)
    b[0x810:0x814] = edc(bytes(b[:0x810])).to_bytes(4, "little")
    b[0x814:0x81C] = bytes(8)
    b[0x81C:0x8C8] = ecc(bytes(b[0x0C:0x81C]), 86, 24, 2, 86)
    b[0x8C8:0x930] = ecc(bytes(b[0x0C:0x8C8]), 52, 43, 86, 88)
    out = bytes(b)
    if not verify_mode1(out):
        raise SystemExit("MODE1 EDC/ECC regeneration failed")
    return out


def extract_asset(raw: Path, lba: int, size: int) -> bytes:
    out = bytearray()
    remain = size
    cur = lba
    with raw.open("rb") as f:
        while remain:
            take = min(USER, remain)
            f.seek(cur * RAW + 16)
            chunk = f.read(take)
            if len(chunk) != take:
                raise SystemExit(f"short re-extraction at LBA {cur}")
            out.extend(chunk)
            remain -= take
            cur += 1
    return bytes(out)


def load_parent_result(path: Path, parent: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("status") != PARENT_STATUS:
        raise SystemExit("Batch273 parent result status mismatch")
    got = shaf(parent)
    if obj.get("output_sha256") != got:
        raise SystemExit("Batch273 parent whole-disc SHA mismatch")
    return obj


def load_legacy_manifests(paths: dict[int, Path]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for batch in sorted(SPECS):
        fmt, expected_count = SPECS[batch]
        obj = json.loads(paths[batch].read_text(encoding="utf-8"))
        if obj.get("format") != fmt:
            raise SystemExit(f"Batch{batch} manifest format mismatch")
        if obj.get("target_disc") != 1:
            raise SystemExit(f"Batch{batch} target disc mismatch")
        if obj.get("parent_bin_sha256") != PRISTINE_SHA:
            raise SystemExit(f"Batch{batch} pristine parent SHA mismatch")
        items = obj.get("replacement_files")
        if not isinstance(items, list) or len(items) != expected_count:
            raise SystemExit(f"Batch{batch} row count mismatch")
        for item in items:
            required = ("iso_path", "lba", "size", "source_sha256", "replacement_sha256")
            if any(k not in item for k in required):
                raise SystemExit(f"Batch{batch} incomplete asset row")
            path = str(item["iso_path"])
            if path in seen:
                raise SystemExit(f"duplicate legacy iso_path: {path}")
            seen.add(path)
            rec = dict(item)
            rec["source_batch"] = batch
            rows.append(rec)
    if len(rows) != 75:
        raise SystemExit(f"legacy Event MES union expected 75 rows, got {len(rows)}")
    return rows


def index_payloads(root: Path, wanted: dict[str, int]) -> tuple[dict[str, bytes], list[dict]]:
    found: dict[str, bytes] = {}
    origins: list[dict] = []
    if not root.exists():
        return found, origins

    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() == ".zip":
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size not in set(wanted.values()):
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        h = shab(data)
        if h in wanted and len(data) == wanted[h] and h not in found:
            found[h] = data
            origins.append({"sha256": h, "kind": "loose", "source": str(p)})

    missing = set(wanted) - set(found)
    if not missing:
        return found, origins

    for zp in root.rglob("*.zip"):
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                for zi in zf.infolist():
                    if zi.is_dir() or zi.file_size not in set(wanted[h] for h in missing):
                        continue
                    data = zf.read(zi)
                    h = shab(data)
                    if h in missing and len(data) == wanted[h]:
                        found[h] = data
                        missing.remove(h)
                        origins.append({"sha256": h, "kind": "zip", "source": str(zp), "member": zi.filename})
                        if not missing:
                            return found, origins
        except (OSError, zipfile.BadZipFile, RuntimeError):
            continue
    return found, origins


def apply_asset(raw: Path, item: dict, payload: bytes, touched: set[int], expected: list[dict]) -> None:
    remain = int(item["size"])
    pos = 0
    lba = int(item["lba"])
    with raw.open("r+b") as f:
        while remain:
            take = min(USER, remain)
            if lba in touched:
                raise SystemExit(f"raw-sector overlap while writing {item['iso_path']} at LBA {lba}")
            f.seek(lba * RAW)
            before = f.read(RAW)
            if len(before) != RAW:
                raise SystemExit(f"short raw sector at LBA {lba}")
            if not verify_mode1(before):
                raise SystemExit(f"parent sector EDC/ECC invalid at LBA {lba}")
            b = bytearray(before)
            b[16:16 + take] = payload[pos:pos + take]
            after = rebuild_mode1(bytes(b))
            expected.append({
                "lba": lba,
                "iso_path": item["iso_path"],
                "before_sha256": shab(before),
                "after_sha256": shab(after),
            })
            f.seek(lba * RAW)
            f.write(after)
            touched.add(lba)
            remain -= take
            pos += take
            lba += 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch274: materialize the 75 legacy exact Event MES assets over Batch273 and close Disc1 Event109")
    ap.add_argument("--batch273", type=Path, required=True)
    ap.add_argument("--batch273-result", type=Path, required=True)
    ap.add_argument("--manifest50", type=Path, required=True)
    ap.add_argument("--manifest51", type=Path, required=True)
    ap.add_argument("--manifest52", type=Path, required=True)
    ap.add_argument("--manifest53", type=Path, required=True)
    ap.add_argument("--manifest54", type=Path, required=True)
    ap.add_argument("--manifest55", type=Path, required=True)
    ap.add_argument("--search-root", type=Path, required=True, help="directory containing loose historical files and/or ZIP archives")
    ap.add_argument("--output", type=Path, default=Path("Sakura_Taisen_2_Disc1_B274_Event109_KO.bin"))
    ap.add_argument("--result", type=Path, default=Path("BATCH274_RESULT.json"))
    a = ap.parse_args()

    load_parent_result(a.batch273_result, a.batch273)
    paths = {n: getattr(a, f"manifest{n}") for n in SPECS}
    rows = load_legacy_manifests(paths)

    states = []
    need: dict[str, int] = {}
    for item in rows:
        data = extract_asset(a.batch273, int(item["lba"]), int(item["size"]))
        got = shab(data)
        if got == item["replacement_sha256"]:
            state = "ALREADY_REPLACEMENT"
        elif got == item["source_sha256"]:
            state = "SOURCE_NEEDS_WRITE"
            need[item["replacement_sha256"]] = int(item["size"])
        else:
            raise SystemExit(f"unsafe parent asset state for {item['iso_path']}: {got}")
        states.append({"iso_path": item["iso_path"], "sha256": got, "state": state})

    payloads, origins = index_payloads(a.search_root, need)
    missing = sorted(set(need) - set(payloads))
    if missing:
        raise SystemExit(f"missing {len(missing)} exact replacement payload(s); first={missing[0]}")

    shutil.copyfile(a.batch273, a.output)
    expected: list[dict] = []
    touched: set[int] = set()
    written_assets = 0
    inherited_assets = 0
    for item, state in zip(rows, states):
        if state["state"] == "ALREADY_REPLACEMENT":
            inherited_assets += 1
            continue
        payload = payloads[item["replacement_sha256"]]
        if len(payload) != int(item["size"]) or shab(payload) != item["replacement_sha256"]:
            raise SystemExit(f"payload gate failed: {item['iso_path']}")
        apply_asset(a.output, item, payload, touched, expected)
        written_assets += 1

    if len(expected) != len(touched):
        raise SystemExit("changed-sector accounting mismatch")

    expected_bad = []
    ecc_bad = []
    with a.output.open("rb") as f:
        for rec in expected:
            f.seek(int(rec["lba"]) * RAW)
            sec = f.read(RAW)
            if shab(sec) != rec["after_sha256"]:
                expected_bad.append(rec["lba"])
            if not verify_mode1(sec):
                ecc_bad.append(rec["lba"])
    if expected_bad:
        raise SystemExit(f"Expected Write failures: {expected_bad[:8]}")
    if ecc_bad:
        raise SystemExit(f"changed-sector EDC/ECC failures: {ecc_bad[:8]}")

    reextract = []
    for item in rows:
        got = shab(extract_asset(a.output, int(item["lba"]), int(item["size"])))
        ok = got == item["replacement_sha256"]
        reextract.append({"iso_path": item["iso_path"], "replacement_sha256": item["replacement_sha256"], "extracted_sha256": got, "pass": ok})
        if not ok:
            raise SystemExit(f"whole-asset re-extraction failed: {item['iso_path']}")

    result = {
        "batch": 274,
        "status": SUCCESS_STATUS,
        "parent_batch": 273,
        "parent_sha256": shaf(a.batch273),
        "legacy_event_rows": 75,
        "legacy_assets_written": written_assets,
        "legacy_assets_already_inherited": inherited_assets,
        "legacy_assets_final_reextraction": "75/75 PASS",
        "event34_inherited_from_batch269": 34,
        "event_mes_completion": "109/109",
        "payload_origin_records": origins,
        "changed_sector_count": len(touched),
        "expected_write_records": len(expected),
        "expected_write": f"{len(expected)}/{len(expected)} PASS",
        "changed_sector_edc_ecc": f"{len(touched)}/{len(touched)} PASS",
        "changed_sector_accounting": "PASS",
        "whole_asset_reextraction": reextract,
        "output_sha256": shaf(a.output),
        "guessed_payload_bytes": False,
    }
    a.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
