#!/usr/bin/env python3
"""Audit Batch110/171 PBOOK raw sectors with computed EDC, ECC-P and ECC-Q.

No legacy code is imported or executed. The literal sector map is parsed by the
Batch171 bridge, patched sidecars are found by SHA-256, and pristine sectors are
read only from the exact Disc 1 image. Both sides must independently pass the
MODE1/2352 mathematical verifier before the 29-sector contract is accepted.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from mode1_2352 import assert_mode1_sector, verify_mode1_sector
from recover_pbook_from_legacy_sector_package import (
    DISC_SHA,
    RAW,
    find_disc,
    find_legacy_patcher,
    load_sidecars,
    sha,
    shaf,
)


def run(root: Path, output: Path) -> dict:
    patcher, sector_map = find_legacy_patcher(root)
    sidecars = load_sidecars(root, sector_map)
    rows = []
    with tempfile.TemporaryDirectory() as td:
        disc = find_disc(root, Path(td))
        if shaf(disc) != DISC_SHA:
            raise RuntimeError("pristine Disc SHA-256 mismatch")
        with disc.open("rb") as source:
            for lba, entry in sorted(sector_map.items()):
                source.seek(lba * RAW)
                original = source.read(RAW)
                patched = sidecars[lba]
                if sha(original) != entry["original_sha256"]:
                    raise RuntimeError(f"Expected Write sector SHA mismatch at LBA {lba}")
                if sha(patched) != entry["patched_sha256"]:
                    raise RuntimeError(f"patched sector SHA mismatch at LBA {lba}")
                if original == patched:
                    raise RuntimeError(f"registered sector is unchanged at LBA {lba}")
                assert_mode1_sector(original, f"original LBA {lba}")
                assert_mode1_sector(patched, f"patched LBA {lba}")
                rows.append({
                    "asset": entry["asset"],
                    "lba": lba,
                    "original_sha256": entry["original_sha256"],
                    "patched_sha256": entry["patched_sha256"],
                    "original_mode1": verify_mode1_sector(original),
                    "patched_mode1": verify_mode1_sector(patched),
                })
    counts = {name: sum(1 for row in rows if row["asset"] == name)
              for name in ("PBOOK_BT", "PBOOK_EC", "PBOOK_RC")}
    if counts != {"PBOOK_BT": 12, "PBOOK_EC": 5, "PBOOK_RC": 12}:
        raise RuntimeError(f"asset sector counts mismatch: {counts}")
    result = {
        "batch": 172,
        "status": "PASS_PBOOK_29_SECTORS_COMPUTED_EDC_ECC",
        "legacy_patcher": str(patcher),
        "legacy_patcher_sha256": shaf(patcher),
        "pristine_disc_sha256": DISC_SHA,
        "sector_count": len(rows),
        "asset_sector_counts": counts,
        "expected_write": "PASS_29_OF_29",
        "original_edc_ecc": "PASS_29_OF_29",
        "patched_edc_ecc": "PASS_29_OF_29",
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path("output/BATCH172_PBOOK_EDC_ECC_AUDIT.json"))
    args = parser.parse_args()
    try:
        result = run(args.root, args.output)
    except Exception as exc:
        result = {"batch": 172, "status": "BLOCKED", "error": str(exc)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
