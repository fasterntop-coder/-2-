#!/usr/bin/env python3
"""Audit that a CD1 candidate changes only sectors authorized by the 91-asset plan.

The pristine Disc is hash-gated. Every raw sector is compared against the
candidate; changed sectors must be inside the exact write-plan ranges. All
candidate sectors touched by the plan are MODE1/2352 EDC/ECC verified, and all
91 assets are re-extracted and checked against replacement SHA-256 values.
No bytes are written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

USER_OFFSET = 16
USER_SIZE = 2048
DISC_SIZE = 659_293_824
DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CHUNK = 4 * 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while block := fp.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    operations = plan.get("operations")
    if plan.get("format") != "ST2-CD1-EXACT-WRITE-PLAN-v1":
        raise ValueError("unsupported write-plan format")
    if not isinstance(operations, list) or len(operations) != 91:
        raise ValueError("exactly 91 write-plan operations required")
    source = plan.get("source_disc", {})
    if source.get("size") != DISC_SIZE or source.get("sha256") != DISC_SHA256:
        raise ValueError("write-plan pristine Disc gate mismatch")
    return plan


def build_authorized_lbas(operations: list[dict[str, Any]]) -> set[int]:
    authorized: set[int] = set()
    for op in operations:
        lba, size = op.get("lba"), op.get("size")
        if not isinstance(lba, int) or lba < 0 or not isinstance(size, int) or size <= 0:
            raise ValueError(f"invalid operation geometry: {op.get('asset')}")
        for sector_lba in range(lba, lba + math.ceil(size / USER_SIZE)):
            if sector_lba in authorized:
                raise ValueError(f"write-plan LBA collision: {sector_lba}")
            authorized.add(sector_lba)
    return authorized


def extract_asset(fp, lba: int, size: int) -> bytes:
    output = bytearray()
    remaining = size
    sector_index = 0
    while remaining:
        fp.seek((lba + sector_index) * RAW_SECTOR_SIZE)
        sector = fp.read(RAW_SECTOR_SIZE)
        if len(sector) != RAW_SECTOR_SIZE:
            raise ValueError(f"short candidate read at LBA {lba + sector_index}")
        if not verify_mode1_sector(sector)["valid"]:
            raise ValueError(f"candidate MODE1/2352 invalid at LBA {lba + sector_index}")
        take = min(USER_SIZE, remaining)
        output.extend(sector[USER_OFFSET:USER_OFFSET + take])
        remaining -= take
        sector_index += 1
    return bytes(output)


def audit(pristine: Path, candidate: Path, plan_path: Path) -> dict[str, Any]:
    plan = load_plan(plan_path)
    operations = plan["operations"]
    authorized = build_authorized_lbas(operations)

    for label, path in (("pristine", pristine), ("candidate", candidate)):
        if path.stat().st_size != DISC_SIZE:
            raise ValueError(f"{label} Disc size mismatch")
    pristine_digest = sha256_file(pristine)
    if pristine_digest != DISC_SHA256:
        raise ValueError("pristine Disc SHA-256 mismatch")

    changed: list[int] = []
    unauthorized: list[int] = []
    invalid_changed: list[int] = []
    total_sectors = DISC_SIZE // RAW_SECTOR_SIZE
    with pristine.open("rb") as src, candidate.open("rb") as dst:
        for lba in range(total_sectors):
            before = src.read(RAW_SECTOR_SIZE)
            after = dst.read(RAW_SECTOR_SIZE)
            if before == after:
                continue
            changed.append(lba)
            if lba not in authorized:
                unauthorized.append(lba)
            if not verify_mode1_sector(after)["valid"]:
                invalid_changed.append(lba)

        asset_results = []
        for op in operations:
            payload = extract_asset(dst, op["lba"], op["size"])
            digest = sha256_bytes(payload)
            if digest != op["replacement_sha256"]:
                raise ValueError(f"91-asset re-extraction mismatch: {op['asset']}")
            asset_results.append({
                "asset": op["asset"],
                "lba": op["lba"],
                "size": op["size"],
                "replacement_sha256": digest,
                "reextraction": "PASS",
            })

    if unauthorized:
        raise ValueError(f"unauthorized changed LBAs: {unauthorized[:32]}")
    if invalid_changed:
        raise ValueError(f"changed sectors with invalid EDC/ECC: {invalid_changed[:32]}")

    return {
        "batch": 210,
        "status": "PASS_CANDIDATE_CHANGES_CONFINED_TO_91_ASSET_PLAN",
        "pristine_disc": {"size": DISC_SIZE, "sha256": pristine_digest},
        "candidate_disc": {"size": DISC_SIZE, "sha256": sha256_file(candidate)},
        "write_plan": {"path": plan_path.as_posix(), "sha256": sha256_file(plan_path), "asset_count": 91},
        "sector_scope": {
            "total_raw_sectors": total_sectors,
            "authorized_sector_count": len(authorized),
            "changed_sector_count": len(changed),
            "changed_lbas_sha256": sha256_bytes("\n".join(map(str, changed)).encode("ascii")),
            "unauthorized_changed_sector_count": 0,
            "changed_sector_mode1_2352_edc_ecc": f"{len(changed)}/{len(changed)} PASS",
        },
        "reextraction": {"status": "91/91 PASS", "assets": asset_results},
        "safety": {"disc_bytes_written": 0, "estimated_or_generated_payload_bytes": 0},
    }


def selftest() -> int:
    ops = [{"asset": "A", "lba": 5, "size": 2048}, {"asset": "B", "lba": 8, "size": 2049}]
    assert build_authorized_lbas(ops) == {5, 8, 9}
    try:
        build_authorized_lbas(ops + [{"asset": "C", "lba": 9, "size": 1}])
    except ValueError:
        pass
    else:
        raise AssertionError("collision self-test failed")
    print("PASS_CD1_CANDIDATE_WRITE_SCOPE_SELFTEST")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pristine-disc", type=Path)
    ap.add_argument("--candidate-disc", type=Path)
    ap.add_argument("--plan", type=Path, default=Path("manifests/CD1_EXACT_WRITE_PLAN.json"))
    ap.add_argument("--report", type=Path, default=Path("output/BATCH210_WRITE_SCOPE_AUDIT.json"))
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.pristine_disc or not args.candidate_disc:
        ap.error("--pristine-disc and --candidate-disc are required")
    result = audit(args.pristine_disc, args.candidate_disc, args.plan)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
