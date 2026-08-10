#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE = 659_293_824
USER_OFF = 16
USER_SIZE = 2048
PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PARENT_B240_SHA = "dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83"
EXPECTED_MANIFESTS = {
    53: ("423bdd882fce078e6cfd10b9b9bf12785a123bbaac6e940910c033c2af962311", 19),
    54: ("b46b5005d3214e9fdf5242ac313bf26a479f3f28b2df712d5559ea97d8bd8554", 8),
    55: ("db9329bffed005551f9ae3f8cf593c9019c7f75483318f5a2efe8c24332f4db5", 15),
}


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


def prepare_asset_writes(raw: bytearray, lba: int, payload: bytes) -> dict[int, bytes]:
    prepared: dict[int, bytes] = {}
    cursor = 0
    idx = 0
    while cursor < len(payload):
        cur_lba = lba + idx
        off = cur_lba * RAW_SECTOR_SIZE
        before = bytes(raw[off:off + RAW_SECTOR_SIZE])
        if len(before) != RAW_SECTOR_SIZE or before[15] != 1:
            raise ValueError(f"parent target is not MODE1/2352 at LBA {cur_lba}")
        if not verify_mode1_sector(before)["valid"]:
            raise ValueError(f"parent target sector EDC/ECC invalid at LBA {cur_lba}")
        sec = bytearray(before)
        take = min(USER_SIZE, len(payload) - cursor)
        sec[USER_OFF:USER_OFF + take] = payload[cursor:cursor + take]
        rebuild_mode1(sec)
        after = bytes(sec)
        if before != after:
            if not verify_mode1_sector(after)["valid"]:
                raise ValueError(f"rebuilt sector EDC/ECC invalid at LBA {cur_lba}")
            prepared[cur_lba] = after
        cursor += take
        idx += 1
    return prepared


def read_legacy_manifest(path: Path, batch: int) -> dict:
    expected_sha, expected_count = EXPECTED_MANIFESTS[batch]
    actual_sha = sha_file(path)
    if actual_sha != expected_sha:
        raise SystemExit(f"FAIL Batch{batch} manifest SHA expected={expected_sha} actual={actual_sha}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    replacements = obj.get("replacement_files")
    if not isinstance(replacements, list) or len(replacements) != expected_count:
        raise SystemExit(f"FAIL Batch{batch} replacement count expected={expected_count}")
    for a in replacements:
        required = {"iso_path", "lba", "size", "source_sha256", "replacement_sha256"}
        if not required.issubset(a):
            raise SystemExit(f"FAIL Batch{batch} malformed replacement entry")
    return obj


def build_target_table(manifests: list[tuple[int, dict]]) -> list[dict]:
    targets: list[dict] = []
    seen_paths: set[str] = set()
    occupied: dict[int, str] = {}
    for batch, obj in manifests:
        for item in obj["replacement_files"]:
            rec = {
                "batch": batch,
                "iso_path": str(item["iso_path"]),
                "lba": int(item["lba"]),
                "size": int(item["size"]),
                "source_sha256": str(item["source_sha256"]).lower(),
                "replacement_sha256": str(item["replacement_sha256"]).lower(),
            }
            if rec["iso_path"] in seen_paths:
                raise SystemExit(f"FAIL duplicate target path {rec['iso_path']}")
            seen_paths.add(rec["iso_path"])
            sectors = (rec["size"] + USER_SIZE - 1) // USER_SIZE
            for lba in range(rec["lba"], rec["lba"] + sectors):
                prev = occupied.get(lba)
                if prev is not None:
                    raise SystemExit(f"FAIL target LBA overlap {lba}: {prev} vs {rec['iso_path']}")
                occupied[lba] = rec["iso_path"]
            targets.append(rec)
    if len(targets) != 42:
        raise SystemExit(f"FAIL combined target count {len(targets)} != 42")
    return targets


def scan_zip(path: Path, wanted: set[str], found: dict[str, Path], tempdir: Path) -> None:
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                with zf.open(info) as src:
                    data = src.read()
                digest = sha_bytes(data)
                if digest in wanted and digest not in found:
                    out = tempdir / f"{digest}.payload"
                    out.write_bytes(data)
                    found[digest] = out
    except (OSError, zipfile.BadZipFile):
        return


def index_payloads(inputs: list[Path], wanted: set[str], tempdir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}

    def consider_file(path: Path) -> None:
        try:
            digest = sha_file(path)
        except OSError:
            return
        if digest in wanted and digest not in found:
            found[digest] = path

    for root in inputs:
        if root.is_dir():
            for p in root.rglob("*"):
                if p.is_file() and p.suffix.lower() == ".zip":
                    scan_zip(p, wanted, found, tempdir)
                elif p.is_file():
                    consider_file(p)
        elif root.is_file() and root.suffix.lower() == ".zip":
            scan_zip(root, wanted, found, tempdir)
        elif root.is_file():
            consider_file(root)
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description="Promote exact Batch53+54+55 late Event MES tail (42 assets) onto verified Batch240 Disc 1")
    ap.add_argument("--parent-bin", required=True, type=Path, help="Exact Batch240 full Disc BIN")
    ap.add_argument("--batch53-manifest", required=True, type=Path)
    ap.add_argument("--batch54-manifest", required=True, type=Path)
    ap.add_argument("--batch55-manifest", required=True, type=Path)
    ap.add_argument("--payload-input", required=True, type=Path, action="append", help="Directory, file, or ZIP; repeatable; payloads matched by SHA-256")
    ap.add_argument("--output-bin", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    if args.parent_bin.stat().st_size != DISC_SIZE:
        raise SystemExit("FAIL Batch240 parent size")
    parent_sha = sha_file(args.parent_bin)
    if parent_sha != PARENT_B240_SHA:
        raise SystemExit(f"FAIL Batch240 parent SHA expected={PARENT_B240_SHA} actual={parent_sha}")

    manifests = [
        (53, read_legacy_manifest(args.batch53_manifest, 53)),
        (54, read_legacy_manifest(args.batch54_manifest, 54)),
        (55, read_legacy_manifest(args.batch55_manifest, 55)),
    ]
    targets = build_target_table(manifests)
    wanted = {a["replacement_sha256"] for a in targets}

    with tempfile.TemporaryDirectory(prefix="st2_b284_") as td:
        payloads = index_payloads(args.payload_input, wanted, Path(td))
        missing = sorted(wanted - set(payloads))
        if missing:
            raise SystemExit("FAIL missing exact replacement payload SHA(s):\n" + "\n".join(missing))

        parent = args.parent_bin.read_bytes()
        out = bytearray(parent)
        expected_write: dict[int, dict] = {}
        asset_audit: list[dict] = []

        for a in targets:
            current = extract_asset(out, a["lba"], a["size"])
            current_sha = sha_bytes(current)
            source_sha = a["source_sha256"]
            target_sha = a["replacement_sha256"]
            if current_sha not in {source_sha, target_sha}:
                raise SystemExit(f"FAIL third variant {a['iso_path']} current={current_sha}")

            state = "already_target"
            if current_sha == source_sha and source_sha != target_sha:
                payload = payloads[target_sha].read_bytes()
                if len(payload) != a["size"] or sha_bytes(payload) != target_sha:
                    raise SystemExit(f"FAIL payload size/SHA {a['iso_path']}")
                prepared = prepare_asset_writes(out, a["lba"], payload)
                for lba, after in prepared.items():
                    off = lba * RAW_SECTOR_SIZE
                    before = bytes(out[off:off + RAW_SECTOR_SIZE])
                    rec = {
                        "lba": lba,
                        "before_sha256": sha_bytes(before),
                        "after_sha256": sha_bytes(after),
                        "asset": a["iso_path"],
                    }
                    prev = expected_write.get(lba)
                    if prev is not None and prev["after_sha256"] != rec["after_sha256"]:
                        raise SystemExit(f"FAIL conflicting Expected Write LBA {lba}")
                    expected_write[lba] = rec
                for lba, after in prepared.items():
                    off = lba * RAW_SECTOR_SIZE
                    out[off:off + RAW_SECTOR_SIZE] = after
                state = "promoted_from_exact_source"

            final_sha = sha_bytes(extract_asset(out, a["lba"], a["size"]))
            if final_sha != target_sha:
                raise SystemExit(f"FAIL whole-asset re-extraction {a['iso_path']}")
            asset_audit.append({
                **a,
                "parent_asset_sha256": current_sha,
                "final_asset_sha256": final_sha,
                "state": state,
                "reextraction": "PASS",
            })

        expected_lbas = sorted(expected_write)
        actual_lbas = []
        for lba in range(DISC_SIZE // RAW_SECTOR_SIZE):
            off = lba * RAW_SECTOR_SIZE
            if parent[off:off + RAW_SECTOR_SIZE] != out[off:off + RAW_SECTOR_SIZE]:
                actual_lbas.append(lba)
        if actual_lbas != expected_lbas:
            raise SystemExit("FAIL changed-sector accounting: actual LBA set != Expected Write LBA set")

        for lba in actual_lbas:
            off = lba * RAW_SECTOR_SIZE
            sec = bytes(out[off:off + RAW_SECTOR_SIZE])
            if not verify_mode1_sector(sec)["valid"]:
                raise SystemExit(f"FAIL final EDC/ECC LBA {lba}")
            rec = expected_write[lba]
            if sha_bytes(parent[off:off + RAW_SECTOR_SIZE]) != rec["before_sha256"]:
                raise SystemExit(f"FAIL Expected Write before SHA LBA {lba}")
            if sha_bytes(sec) != rec["after_sha256"]:
                raise SystemExit(f"FAIL Expected Write after SHA LBA {lba}")

        controls = manifests[-1][1].get("reviewed_unchanged_control_files", [])
        control_audit = []
        for c in controls:
            name = str(c.get("file", ""))
            lba = int(c["lba"])
            size = int(c["size"])
            expected = str(c["sha256"]).lower()
            actual = sha_bytes(extract_asset(out, lba, size))
            if actual != expected:
                raise SystemExit(f"FAIL unchanged control {name} expected={expected} actual={actual}")
            control_audit.append({"file": name, "lba": lba, "size": size, "sha256": actual, "status": "PASS_UNCHANGED"})

        args.output_bin.parent.mkdir(parents=True, exist_ok=True)
        args.output_bin.write_bytes(out)
        output_sha = sha_file(args.output_bin)
        report = {
            "batch": 284,
            "status": "PASS_BATCH284_EVENT42_LATE_TAIL_PHYSICAL_PROMOTION",
            "pristine_reference_sha256": PRISTINE_SHA,
            "parent_batch": 240,
            "parent_sha256": parent_sha,
            "output_sha256": output_sha,
            "legacy_manifest_sha256": {str(b): EXPECTED_MANIFESTS[b][0] for b in (53, 54, 55)},
            "replacement_assets": 42,
            "asset_reextraction": "42/42 PASS",
            "unchanged_controls": f"{len(control_audit)}/{len(control_audit)} PASS",
            "guessed_payload_bytes": 0,
            "expected_write": [expected_write[x] for x in expected_lbas],
            "changed_raw_sectors": len(actual_lbas),
            "changed_lbas": actual_lbas,
            "changed_sector_accounting": "PASS",
            "changed_sector_edc_ecc": f"{len(actual_lbas)}/{len(actual_lbas)} PASS",
            "asset_audit": asset_audit,
            "control_audit": control_audit,
            "physical_scope": {
                "parent_assets": 94,
                "new_event_assets": 42,
                "candidate_assets": 136,
                "event_mes_logical_completion": "109/109",
                "event_records_logical_completion": "1094/1094"
            }
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(report["status"])
        print(f"output_sha256={output_sha}")
        print(f"changed_raw_sectors={len(actual_lbas)}")
        print("event_tail_assets=42/42")
        print("physical_assets=136")


if __name__ == "__main__":
    main()
