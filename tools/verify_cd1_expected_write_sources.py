#!/usr/bin/env python3
"""Verify all 91 Expected Write source hashes against the pristine CD1 image.

The verifier is read-only. It binds each operation's source_sha256 to bytes
re-extracted from the exact pristine MODE1/2352 Disc, verifies operation geometry,
rejects missing source hashes, and verifies EDC/ECC for every source sector read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, BinaryIO

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

USER_OFFSET = 16
USER_SIZE = 2048
EXPECTED_COUNT = 91
DISC_SIZE = 659_293_824
DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PLAN_FORMAT = "ST2-CD1-EXACT-WRITE-PLAN-v1"
HEX = set("0123456789abcdef")
CHUNK = 4 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while block := fp.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in HEX for c in value):
        raise ValueError(f"invalid lowercase SHA-256 for {label}: {value!r}")
    return value


def require_int(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if value < 0 if allow_zero else value <= 0:
        raise ValueError(f"invalid {label}: {value}")
    return value


def load_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("write plan top level must be an object")
    if plan.get("format") != PLAN_FORMAT or plan.get("asset_count") != EXPECTED_COUNT:
        raise ValueError("write-plan identity/count mismatch")
    source = plan.get("source_disc")
    if not isinstance(source, dict):
        raise ValueError("write-plan source_disc missing")
    if source.get("size") != DISC_SIZE or source.get("sha256") != DISC_SHA256:
        raise ValueError("write-plan pristine Disc gate mismatch")
    if source.get("format") != "MODE1/2352" or source.get("raw_sector_size") != RAW_SECTOR_SIZE:
        raise ValueError("write-plan raw-sector format mismatch")
    if source.get("user_sector_size") != USER_SIZE:
        raise ValueError("write-plan user-sector size mismatch")
    operations = plan.get("operations")
    if not isinstance(operations, list) or len(operations) != EXPECTED_COUNT:
        raise ValueError("write plan must contain exactly 91 operations")
    return plan


def validate_operations(operations: list[Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    names: set[str] = set()
    occupied: set[int] = set()
    for index, raw in enumerate(operations):
        if not isinstance(raw, dict):
            raise ValueError(f"operation {index} is not an object")
        asset = raw.get("asset")
        if not isinstance(asset, str) or not asset:
            raise ValueError(f"operation {index} asset missing")
        key = asset.replace("\\", "/").upper()
        if key in names:
            raise ValueError(f"duplicate asset: {asset}")
        names.add(key)

        lba = require_int(raw.get("lba"), f"{asset}:lba", allow_zero=True)
        size = require_int(raw.get("size"), f"{asset}:size")
        sectors = math.ceil(size / USER_SIZE)
        if raw.get("user_sectors") != sectors:
            raise ValueError(f"{asset}: user_sectors mismatch")
        if raw.get("end_lba_exclusive") != lba + sectors:
            raise ValueError(f"{asset}: end_lba_exclusive mismatch")
        if raw.get("write_policy") != "EXPECTED_WRITE_EXACT_HASH_ONLY":
            raise ValueError(f"{asset}: write_policy mismatch")
        source_sha = require_sha(raw.get("source_sha256"), f"{asset}:source_sha256")
        replacement_sha = require_sha(raw.get("replacement_sha256"), f"{asset}:replacement_sha256")
        if source_sha == replacement_sha:
            raise ValueError(f"{asset}: source and replacement SHA-256 are identical")
        if lba + sectors > DISC_SIZE // RAW_SECTOR_SIZE:
            raise ValueError(f"{asset}: operation exceeds Disc boundary")
        for sector_lba in range(lba, lba + sectors):
            if sector_lba in occupied:
                raise ValueError(f"operation LBA collision: {sector_lba}")
            occupied.add(sector_lba)
        validated.append({
            "asset": asset.replace("\\", "/"),
            "lba": lba,
            "size": size,
            "user_sectors": sectors,
            "source_sha256": source_sha,
            "replacement_sha256": replacement_sha,
        })
    return validated


def extract_source(fp: BinaryIO, op: dict[str, Any]) -> tuple[bytes, list[int]]:
    output = bytearray()
    verified_lbas: list[int] = []
    remaining = op["size"]
    for offset in range(op["user_sectors"]):
        lba = op["lba"] + offset
        fp.seek(lba * RAW_SECTOR_SIZE)
        sector = fp.read(RAW_SECTOR_SIZE)
        if len(sector) != RAW_SECTOR_SIZE:
            raise ValueError(f"short pristine read at LBA {lba}")
        result = verify_mode1_sector(sector)
        if not result["valid"]:
            raise ValueError(f"pristine MODE1/2352 EDC/ECC failure at LBA {lba}")
        take = min(USER_SIZE, remaining)
        output.extend(sector[USER_OFFSET:USER_OFFSET + take])
        remaining -= take
        verified_lbas.append(lba)
    if remaining != 0:
        raise AssertionError("source extraction length accounting failure")
    return bytes(output), verified_lbas


def verify(pristine: Path, plan_path: Path) -> dict[str, Any]:
    if pristine.stat().st_size != DISC_SIZE:
        raise ValueError("pristine Disc size mismatch")
    pristine_sha = sha256_file(pristine)
    if pristine_sha != DISC_SHA256:
        raise ValueError("pristine Disc SHA-256 mismatch")

    plan = load_plan(plan_path)
    operations = validate_operations(plan["operations"])
    records = []
    verified_sector_count = 0
    with pristine.open("rb") as fp:
        for op in operations:
            payload, lbas = extract_source(fp, op)
            digest = hashlib.sha256(payload).hexdigest()
            if digest != op["source_sha256"]:
                raise ValueError(
                    f"Expected Write source mismatch for {op['asset']}: "
                    f"plan={op['source_sha256']} pristine={digest}"
                )
            verified_sector_count += len(lbas)
            records.append({
                "asset": op["asset"],
                "lba": op["lba"],
                "size": op["size"],
                "user_sectors": op["user_sectors"],
                "source_sha256": digest,
                "expected_write_source": "PASS",
                "mode1_2352_edc_ecc": f"{len(lbas)}/{len(lbas)} PASS",
            })

    return {
        "batch": 216,
        "status": "PASS_91_ASSET_PRISTINE_EXPECTED_WRITE_SOURCES",
        "pristine_disc": {"size": DISC_SIZE, "sha256": pristine_sha},
        "write_plan": {"path": plan_path.as_posix(), "sha256": sha256_file(plan_path)},
        "asset_count": len(records),
        "source_sector_reads": verified_sector_count,
        "assets": records,
        "gates": {
            "all_source_sha256_present": "91/91 PASS",
            "pristine_source_reextraction": "91/91 PASS",
            "operation_geometry": "91/91 PASS",
            "expected_write_policy": "91/91 PASS",
            "mode1_2352_edc_ecc": f"{verified_sector_count}/{verified_sector_count} PASS",
        },
        "safety": {"estimated_or_generated_payload_bytes": 0, "disc_bytes_written": 0},
    }


def selftest() -> None:
    ops = []
    for i in range(EXPECTED_COUNT):
        ops.append({
            "asset": f"SAKURA1/A{i:02d}.BIN",
            "lba": i * 2,
            "size": 2049,
            "user_sectors": 2,
            "end_lba_exclusive": i * 2 + 2,
            "source_sha256": f"{i + 1:064x}"[-64:],
            "replacement_sha256": f"{i + 1000:064x}"[-64:],
            "write_policy": "EXPECTED_WRITE_EXACT_HASH_ONLY",
        })
    assert len(validate_operations(ops)) == EXPECTED_COUNT

    bad = json.loads(json.dumps(ops))
    bad[3]["source_sha256"] = None
    try:
        validate_operations(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("missing source_sha256 was accepted")

    bad = json.loads(json.dumps(ops))
    bad[4]["end_lba_exclusive"] += 1
    try:
        validate_operations(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid end_lba_exclusive was accepted")

    bad = json.loads(json.dumps(ops))
    bad[5]["write_policy"] = "UNSAFE"
    try:
        validate_operations(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid write_policy was accepted")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pristine-disc", type=Path)
    ap.add_argument("--plan", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    ap.add_argument("--output", type=Path, default=Path("output/BATCH216_EXPECTED_WRITE_SOURCES.json"))
    args = ap.parse_args()
    if args.selftest:
        selftest()
        print("PASS_91_ASSET_PRISTINE_EXPECTED_WRITE_SOURCES_SELFTEST")
        return 0
    if args.pristine_disc is None:
        ap.error("--pristine-disc is required")
    result = verify(args.pristine_disc, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
