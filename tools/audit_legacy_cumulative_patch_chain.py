#!/usr/bin/env python3
"""Audit cumulative raw-sector patch packages without applying guessed bytes.

The tool reads patch_manifest.json files, verifies each payload range's size and
SHA-256, checks output SHA metadata, and reports any sector dropped by a later
package.  It does not write a Disc image.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

RAW_SECTOR_SIZE = 2352


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_package(root: Path) -> dict[str, Any]:
    manifest_path = root / "patch_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sectors: dict[int, str] = {}
    ranges = manifest.get("payload_ranges")
    if not isinstance(ranges, list):
        raise ValueError(f"payload_ranges missing: {manifest_path}")

    for item in ranges:
        start = int(item["start_sector"])
        count = int(item["sector_count"])
        payload_path = root / item["file"]
        payload = payload_path.read_bytes()
        if len(payload) != count * RAW_SECTOR_SIZE:
            raise ValueError(f"payload size mismatch: {payload_path}")
        digest = sha256_bytes(payload)
        if digest != item["sha256"]:
            raise ValueError(f"payload SHA mismatch: {payload_path}")
        for index in range(count):
            lba = start + index
            sector = payload[index * RAW_SECTOR_SIZE:(index + 1) * RAW_SECTOR_SIZE]
            sector_sha = sha256_bytes(sector)
            previous = sectors.get(lba)
            if previous is not None and previous != sector_sha:
                raise ValueError(f"conflicting writes inside package at LBA {lba}")
            sectors[lba] = sector_sha

    return {
        "name": root.name,
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "source_bin_sha256": manifest.get("source_bin_sha256"),
        "output_bin_sha256": manifest.get("output_bin_sha256"),
        "sector_count": len(sectors),
        "sectors": sectors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packages", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/BATCH207_CHAIN_AUDIT.json"))
    args = parser.parse_args()

    loaded = [load_package(path) for path in args.packages]
    if len(loaded) < 2:
        raise ValueError("at least two packages are required")

    source_hashes = {item["source_bin_sha256"] for item in loaded}
    if len(source_hashes) != 1:
        raise ValueError("packages do not share one pristine source SHA")

    transitions = []
    dropped_total = 0
    for previous, current in zip(loaded, loaded[1:]):
        prev_lbas = set(previous["sectors"])
        cur_lbas = set(current["sectors"])
        dropped = sorted(prev_lbas - cur_lbas)
        added = sorted(cur_lbas - prev_lbas)
        changed = sorted(
            lba for lba in prev_lbas & cur_lbas
            if previous["sectors"][lba] != current["sectors"][lba]
        )
        dropped_total += len(dropped)
        transitions.append({
            "from": previous["name"],
            "to": current["name"],
            "previous_sector_count": len(prev_lbas),
            "current_sector_count": len(cur_lbas),
            "added_sector_count": len(added),
            "dropped_sector_count": len(dropped),
            "dropped_lbas": dropped,
            "overwritten_existing_sector_count": len(changed),
            "overwritten_existing_lbas": changed,
            "previous_lbas_preserved": not dropped,
        })

    result = {
        "format": "ST2-LEGACY-CUMULATIVE-PATCH-CHAIN-AUDIT-v1",
        "status": "PASS_MONOTONIC_CHAIN" if dropped_total == 0 else "FAIL_DROPPED_PREVIOUS_SECTORS",
        "source_bin_sha256": next(iter(source_hashes)),
        "packages": [
            {key: value for key, value in item.items() if key != "sectors"}
            for item in loaded
        ],
        "transitions": transitions,
        "safety": {
            "estimated_payload_bytes": 0,
            "disc_bytes_written": 0,
            "payload_selection": "MANIFEST_SIZE_AND_SHA256_ONLY",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"])
    return 0 if dropped_total == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
