#!/usr/bin/env python3
"""Extract a normalized exact-sector manifest from legacy batch apply scripts.

The historical ST2 batch scripts embed a top-level SECTORS/M dictionary plus
source/output image gates. This parser uses Python's AST and literal_eval only;
it never executes the legacy script. The normalized JSON can be consumed by
exact recovery/build tools while preserving Expected Write and SHA-256 gates.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

SUPPORTED_MAP_NAMES = ("SECTORS", "SEC", "M")
SOURCE_SHA_NAMES = ("SOURCE_SHA", "SS", "SHA")
OUTPUT_SHA_NAMES = ("OUTPUT_SHA", "OS")
SOURCE_SIZE_NAMES = ("SOURCE_SIZE", "SIZE", "SZ")
SECTOR_SIZE_NAMES = ("RS", "RAW")


def literal_assignments(text: str) -> dict[str, Any]:
    tree = ast.parse(text)
    out: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            out[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return out


def first(mapping: dict[str, Any], names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def normalize(script: Path) -> dict[str, Any]:
    values = literal_assignments(script.read_text(encoding="utf-8-sig"))
    sectors = first(values, SUPPORTED_MAP_NAMES)
    if not isinstance(sectors, dict) or not sectors:
        raise ValueError("no literal SECTORS/SEC/M dictionary found")

    normalized: list[dict[str, Any]] = []
    for raw_lba, entry in sectors.items():
        if not isinstance(entry, dict):
            raise ValueError(f"LBA {raw_lba}: entry is not a dictionary")
        lba = int(raw_lba)
        original = str(entry.get("original_sha256", "")).lower()
        patched = str(entry.get("patched_sha256", "")).lower()
        if len(original) != 64 or len(patched) != 64:
            raise ValueError(f"LBA {lba}: missing SHA-256 gate")
        normalized.append(
            {
                "raw_lba": lba,
                "asset": entry.get("asset"),
                "payload_path": entry.get("file"),
                "expected_original_sha256": original,
                "patched_sha256": patched,
            }
        )
    normalized.sort(key=lambda item: item["raw_lba"])
    if len({item["raw_lba"] for item in normalized}) != len(normalized):
        raise ValueError("duplicate raw LBA")

    sector_size = int(first(values, SECTOR_SIZE_NAMES, 2352))
    return {
        "format": "st2-exact-sector-manifest-v1",
        "source_script": script.name,
        "source_image_size": int(first(values, SOURCE_SIZE_NAMES, 0)),
        "source_image_sha256": str(first(values, SOURCE_SHA_NAMES, "")).lower(),
        "target_image_sha256": str(first(values, OUTPUT_SHA_NAMES, "")).lower(),
        "raw_sector_size": sector_size,
        "sector_count": len(normalized),
        "lba_min": normalized[0]["raw_lba"],
        "lba_max": normalized[-1]["raw_lba"],
        "sectors": normalized,
        "safety": {
            "legacy_script_executed": False,
            "expected_write_required": True,
            "patched_payload_sha_required": True,
            "whole_output_sha_required": True,
        },
    }


def selftest() -> dict[str, Any]:
    sample = '''SOURCE_SIZE=659293824;SOURCE_SHA="''' + "a" * 64 + '''";OUTPUT_SHA="''' + "b" * 64 + '''";RS=2352\nSECTORS={"20":{"file":"PATCH_SECTORS/x.bin","original_sha256":"''' + "c" * 64 + '''","patched_sha256":"''' + "d" * 64 + '''","asset":"SYS00"},"10":{"file":"PATCH_SECTORS/y.bin","original_sha256":"''' + "e" * 64 + '''","patched_sha256":"''' + "f" * 64 + '''","asset":"PBOOK_BT"}}\n'''
    tree = literal_assignments(sample)
    sectors = tree["SECTORS"]
    passed = (
        tree["SOURCE_SIZE"] == 659293824
        and len(sectors) == 2
        and sectors["10"]["asset"] == "PBOOK_BT"
    )
    return {"status": "PASS" if passed else "FAIL", "sector_count": len(sectors)}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("script", type=Path)
    extract.add_argument("output", type=Path)
    sub.add_parser("selftest")
    args = parser.parse_args()

    if args.command == "selftest":
        result = selftest()
    else:
        result = normalize(args.script)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result.get("status", "PASS")).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
