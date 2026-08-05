#!/usr/bin/env python3
"""Assemble exact SYSTEM/SYS14 MES assets from recovered record payloads.

The source asset, extracted fixed-allocation layout and recovered-record report
are all independently gated. Control records remain byte-identical. Translated
records are written only when their recovered record SHA matches the layout
oracle, and the completed asset is emitted only when its whole-file SHA-256
matches the historical target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"JSON object required: {path}")
    return doc


def normalize_layout(doc: dict[str, Any], bank: str) -> dict[str, Any]:
    root = doc.get(bank, doc)
    if not isinstance(root, dict):
        raise ValueError(f"layout does not contain {bank}")
    return root


def recovered_records(doc: dict[str, Any], bank: str) -> dict[int, bytes]:
    if doc.get("status") != "PASS_ALL_EXACT_RECORDS_RECOVERED":
        raise ValueError("record recovery report did not pass")
    result: dict[int, bytes] = {}
    for row in doc.get("results", []):
        if str(row.get("status")) != "PASS_EXACT_RECORD_RECOVERED":
            raise ValueError("non-passing record in recovery report")
        if str(row.get("bank", "")).upper() != bank:
            continue
        record = int(row["record"])
        payload = bytes.fromhex(str(row["record_hex"]))
        digest = str(row["sha256"]).lower()
        if sha256(payload) != digest:
            raise ValueError(f"recovered record payload SHA mismatch {bank}:{record}")
        if record in result:
            raise ValueError(f"duplicate recovered record {bank}:{record}")
        result[record] = payload
    return result


def assemble(source: Path, layout_path: Path, recovery_path: Path, bank: str,
             source_sha256: str, target_sha256: str, output: Path) -> dict[str, Any]:
    bank = bank.upper()
    source_bytes = source.read_bytes()
    actual_source = sha256(source_bytes)
    if actual_source != source_sha256.lower():
        raise RuntimeError(f"source asset SHA mismatch: {actual_source}")

    layout_doc = load_json(layout_path)
    layout = normalize_layout(layout_doc, bank)
    records = recovered_records(load_json(recovery_path), bank)
    candidate = bytearray(source_bytes)
    written: list[int] = []

    for record, payload in sorted(records.items()):
        key = str(record)
        if key not in layout:
            raise RuntimeError(f"layout missing {bank}:{record}")
        item = layout[key]
        offset = int(item["offset"])
        allocation = int(item["allocation_size"])
        oracle = str(item.get("candidate_record_sha256", item.get("target_sha256", ""))).lower()
        if len(payload) != allocation:
            raise RuntimeError(f"allocation mismatch {bank}:{record}")
        if oracle and sha256(payload) != oracle:
            raise RuntimeError(f"layout candidate SHA mismatch {bank}:{record}")
        if offset < 0 or offset + allocation > len(candidate):
            raise RuntimeError(f"record range outside source asset {bank}:{record}")
        candidate[offset:offset + allocation] = payload
        written.append(record)

    target = sha256(candidate)
    if target != target_sha256.lower():
        raise RuntimeError(f"whole asset SHA mismatch: {target}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(candidate)
    return {
        "status": "PASS_EXACT_MES_ASSET_ASSEMBLED",
        "bank": bank,
        "source_sha256": actual_source,
        "target_sha256": target,
        "translated_records_written": len(written),
        "written_records": written,
        "control_records_preserved": len(layout) - len(written),
        "output": str(output),
    }


def selftest() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = bytearray(range(128))
        record0 = bytes([0xAA] * 16)
        record2 = bytes([0x55] * 20)
        target = bytearray(source)
        target[16:32] = record0
        target[64:84] = record2
        source_path = root / "SYSTEM.MES"
        source_path.write_bytes(source)
        layout = {
            "SYSTEM": {
                "0": {"offset": 16, "allocation_size": 16, "candidate_record_sha256": sha256(record0)},
                "1": {"offset": 32, "allocation_size": 12},
                "2": {"offset": 64, "allocation_size": 20, "candidate_record_sha256": sha256(record2)},
            }
        }
        recovery = {
            "status": "PASS_ALL_EXACT_RECORDS_RECOVERED",
            "results": [
                {"status": "PASS_EXACT_RECORD_RECOVERED", "bank": "SYSTEM", "record": 0,
                 "sha256": sha256(record0), "record_hex": record0.hex()},
                {"status": "PASS_EXACT_RECORD_RECOVERED", "bank": "SYSTEM", "record": 2,
                 "sha256": sha256(record2), "record_hex": record2.hex()},
            ],
        }
        layout_path = root / "layout.json"
        recovery_path = root / "recovery.json"
        layout_path.write_text(json.dumps(layout), encoding="utf-8")
        recovery_path.write_text(json.dumps(recovery), encoding="utf-8")
        output = root / "out.MES"
        result = assemble(source_path, layout_path, recovery_path, "SYSTEM", sha256(source), sha256(target), output)
        negative = False
        try:
            assemble(source_path, layout_path, recovery_path, "SYSTEM", sha256(source), "0" * 64, root / "bad.MES")
        except RuntimeError:
            negative = not (root / "bad.MES").exists()
        passed = result["status"].startswith("PASS") and output.read_bytes() == target and negative
        return {"status": "PASS" if passed else "FAIL", "roundtrip": passed, "negative_gate": negative}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("assemble")
    run.add_argument("--source", required=True, type=Path)
    run.add_argument("--layout", required=True, type=Path)
    run.add_argument("--recovery", required=True, type=Path)
    run.add_argument("--bank", required=True, choices=["SYSTEM", "SYS14"])
    run.add_argument("--source-sha256", required=True)
    run.add_argument("--target-sha256", required=True)
    run.add_argument("--output", required=True, type=Path)
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else assemble(
        args.source, args.layout, args.recovery, args.bank,
        args.source_sha256, args.target_sha256, args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
