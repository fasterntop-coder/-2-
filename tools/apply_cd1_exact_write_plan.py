#!/usr/bin/env python3
"""Apply the 91-asset CD1 exact write plan with strict raw-sector gates.

No guessed bytes are accepted. Every operation requires an exact replacement
payload, optional source Expected Write verification, MODE1/2352 regeneration,
and post-write re-extraction verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

USER_OFFSET = 16
USER_SIZE = 2048
DISC_SIZE = 659_293_824
DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CHUNK = 4 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rebuild_mode1(sector: bytearray) -> None:
    if len(sector) != RAW_SECTOR_SIZE or sector[15] != 1:
        raise ValueError("target is not a MODE1/2352 sector")
    sector[0x810:0x814] = edc(bytes(sector[:0x810])).to_bytes(4, "little")
    sector[0x814:0x81C] = bytes(8)
    sector[0x81C:0x8C8] = _ecc_compute(bytes(sector[0x0C:0x81C]), 86, 24, 2, 86)
    sector[0x8C8:0x930] = _ecc_compute(bytes(sector[0x0C:0x8C8]), 52, 43, 86, 88)
    if not verify_mode1_sector(bytes(sector))["valid"]:
        raise ValueError("rebuilt MODE1/2352 sector failed EDC/ECC")


def extract_asset(fp, lba: int, size: int) -> bytes:
    out = bytearray()
    remaining = size
    sector_index = 0
    while remaining:
        fp.seek((lba + sector_index) * RAW_SECTOR_SIZE)
        sector = fp.read(RAW_SECTOR_SIZE)
        if len(sector) != RAW_SECTOR_SIZE:
            raise ValueError(f"short sector read at LBA {lba + sector_index}")
        if not verify_mode1_sector(sector)["valid"]:
            raise ValueError(f"source sector EDC/ECC invalid at LBA {lba + sector_index}")
        take = min(USER_SIZE, remaining)
        out.extend(sector[USER_OFFSET:USER_OFFSET + take])
        remaining -= take
        sector_index += 1
    return bytes(out)


def write_asset(fp, lba: int, payload: bytes) -> list[int]:
    changed: list[int] = []
    offset = 0
    sector_index = 0
    while offset < len(payload):
        raw_lba = lba + sector_index
        fp.seek(raw_lba * RAW_SECTOR_SIZE)
        original = fp.read(RAW_SECTOR_SIZE)
        if len(original) != RAW_SECTOR_SIZE:
            raise ValueError(f"short sector read at LBA {raw_lba}")
        if not verify_mode1_sector(original)["valid"]:
            raise ValueError(f"pre-write EDC/ECC invalid at LBA {raw_lba}")
        sector = bytearray(original)
        take = min(USER_SIZE, len(payload) - offset)
        sector[USER_OFFSET:USER_OFFSET + take] = payload[offset:offset + take]
        rebuild_mode1(sector)
        if bytes(sector) != original:
            fp.seek(raw_lba * RAW_SECTOR_SIZE)
            fp.write(sector)
            changed.append(raw_lba)
        offset += take
        sector_index += 1
    return changed


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"top level must be object: {path}")
    return value


def resolve_payload(root: Path, op: dict[str, Any]) -> Path:
    digest = op["replacement_sha256"]
    candidates = [root / digest, root / f"{digest}.bin", root / Path(op["asset"]).name]
    for path in candidates:
        if path.is_file() and path.stat().st_size == op["size"] and sha256_file(path) == digest:
            return path
    raise FileNotFoundError(f"exact replacement payload missing: {op['asset']} {digest}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    ap.add_argument("--source-disc", type=Path, required=True)
    ap.add_argument("--payload-root", type=Path, required=True)
    ap.add_argument("--output-disc", type=Path, required=True)
    ap.add_argument("--report", type=Path, default=Path("output/BATCH205_APPLY_RESULT.json"))
    args = ap.parse_args()

    plan = load_json(args.plan)
    ops = plan.get("operations")
    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1" or not isinstance(ops, list) or len(ops) != 91:
        raise ValueError("exact 91-asset write plan required")
    if args.source_disc.stat().st_size != DISC_SIZE or sha256_file(args.source_disc) != DISC_SHA256:
        raise ValueError("pristine Disc size/SHA-256 gate failed")

    payloads = [(op, resolve_payload(args.payload_root, op)) for op in ops]
    args.output_disc.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.source_disc, args.output_disc)

    results = []
    all_changed: set[int] = set()
    try:
        with args.output_disc.open("r+b") as fp:
            for op, payload_path in payloads:
                before = extract_asset(fp, op["lba"], op["size"])
                source_sha = op.get("source_sha256")
                if source_sha and sha256_bytes(before) != source_sha:
                    raise ValueError(f"Expected Write source mismatch: {op['asset']}")
                payload = payload_path.read_bytes()
                if sha256_bytes(payload) != op["replacement_sha256"]:
                    raise ValueError(f"replacement SHA mismatch: {op['asset']}")
                changed = write_asset(fp, op["lba"], payload)
                after = extract_asset(fp, op["lba"], op["size"])
                if sha256_bytes(after) != op["replacement_sha256"]:
                    raise ValueError(f"re-extraction mismatch: {op['asset']}")
                if all_changed.intersection(changed):
                    raise ValueError(f"changed-sector collision: {op['asset']}")
                all_changed.update(changed)
                results.append({"asset": op["asset"], "lba": op["lba"], "size": op["size"], "replacement_sha256": op["replacement_sha256"], "changed_lbas": changed, "expected_write": "PASS", "reextraction": "PASS"})
    except Exception:
        args.output_disc.unlink(missing_ok=True)
        raise

    report = {"batch": 205, "status": "PASS_91_OF_91_EXACT_WRITE_EDC_ECC_REEXTRACTION", "source_disc_sha256": DISC_SHA256, "output_disc_sha256": sha256_file(args.output_disc), "asset_count": len(results), "changed_sector_count": len(all_changed), "assets": results, "gates": {"expected_write": "91/91 PASS", "mode1_2352_edc_ecc": "ALL CHANGED SECTORS PASS", "reextraction": "91/91 PASS", "estimated_payload_bytes": 0}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
