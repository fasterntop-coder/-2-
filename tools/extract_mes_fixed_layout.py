#!/usr/bin/env python3
"""Derive exact MES record allocations from a pristine asset and SHA oracles.

This removes the hand-authored layout JSON dependency from the Batch 148 fixed-
allocation recovery path. Candidate offset-table interpretations are discovered
without trusting guessed bytes; a layout is emitted only when every source
record slice matches the historical source_record_sha256 oracle.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Oracle:
    record: int
    source_sha256: str


def load_oracles(path: Path, bank: str, count: int) -> list[Oracle]:
    rows: dict[int, Oracle] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if str(row.get("bank", "")).strip().upper() != bank.upper():
                continue
            record = int(row["record"])
            digest = str(row["source_record_sha256"]).strip().lower()
            if not 0 <= record < count or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError(f"invalid oracle at {bank}:{record}")
            if record in rows:
                raise ValueError(f"duplicate oracle at {bank}:{record}")
            rows[record] = Oracle(record, digest)
    if set(rows) != set(range(count)):
        missing = sorted(set(range(count)) - set(rows))
        raise ValueError(f"incomplete oracle coverage for {bank}: {missing[:8]}")
    return [rows[i] for i in range(count)]


def unpack_offsets(data: bytes, table_offset: int, count: int, width: int, endian: str) -> tuple[int, ...]:
    fmt = ("<" if endian == "little" else ">") + ("H" if width == 2 else "I") * count
    size = width * count
    if table_offset < 0 or table_offset + size > len(data):
        raise ValueError("offset table outside asset")
    return tuple(int(x) for x in struct.unpack(fmt, data[table_offset : table_offset + size]))


def absolute_offsets(raw: Iterable[int], base: int, mode: str) -> tuple[int, ...]:
    return tuple(value + base if mode == "relative" else value for value in raw)


def structurally_valid(offsets: tuple[int, ...], message_base: int, message_end: int) -> bool:
    return (
        bool(offsets)
        and offsets[0] >= message_base
        and all(a < b for a, b in zip(offsets, offsets[1:]))
        and offsets[-1] < message_end
        and all((value & 1) == 0 for value in offsets)
    )


def verify_layout(data: bytes, offsets: tuple[int, ...], message_end: int, oracles: list[Oracle]) -> list[dict[str, object]] | None:
    ends = offsets[1:] + (message_end,)
    records: list[dict[str, object]] = []
    for oracle, start, end in zip(oracles, offsets, ends):
        if not (0 <= start < end <= len(data)):
            return None
        record = data[start:end]
        if sha256(record) != oracle.source_sha256:
            return None
        if len(record) < 4:
            return None
        records.append({
            "offset": start,
            "allocation_size": end - start,
            "metadata_hex": record[:4].hex(),
            "source_record_sha256": oracle.source_sha256,
        })
    return records


def discover(data: bytes, oracles: list[Oracle], message_base: int, message_end: int, search_limit: int) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    count = len(oracles)
    for width in (2, 4):
        maximum = min(search_limit, len(data) - width * count)
        for table_offset in range(0, maximum + 1, width):
            for endian in ("little", "big"):
                try:
                    raw = unpack_offsets(data, table_offset, count, width, endian)
                except (ValueError, struct.error):
                    continue
                for mode, base in (("relative", message_base), ("absolute", 0)):
                    offsets = absolute_offsets(raw, base, mode)
                    if not structurally_valid(offsets, message_base, message_end):
                        continue
                    records = verify_layout(data, offsets, message_end, oracles)
                    if records is not None:
                        matches.append({
                            "table_offset": table_offset,
                            "offset_width": width,
                            "endian": endian,
                            "offset_mode": mode,
                            "message_base": message_base,
                            "message_end": message_end,
                            "records": records,
                        })
    return matches


def extract(asset: Path, audit: Path, bank: str, output: Path, expected_asset_sha256: str | None,
            count: int, message_base: int, message_end: int, search_limit: int) -> dict[str, object]:
    data = asset.read_bytes()
    actual = sha256(data)
    if expected_asset_sha256 and actual != expected_asset_sha256.lower():
        return {"status": "BLOCKED_SOURCE_ASSET_SHA_MISMATCH", "actual_sha256": actual, "output_emitted": False}
    if message_end > len(data):
        return {"status": "BLOCKED_MESSAGE_REGION_OUTSIDE_ASSET", "asset_size": len(data), "output_emitted": False}
    oracles = load_oracles(audit, bank, count)
    matches = discover(data, oracles, message_base, message_end, search_limit)
    if len(matches) != 1:
        return {
            "status": "BLOCKED_NO_UNIQUE_EXACT_LAYOUT" if not matches else "BLOCKED_AMBIGUOUS_EXACT_LAYOUT",
            "exact_matches": len(matches),
            "output_emitted": False,
        }
    match = matches[0]
    layout = {
        "schema": "st2-mes-fixed-layout-v1",
        "bank": bank.upper(),
        "asset_sha256": actual,
        "record_count": count,
        "table": {k: match[k] for k in ("table_offset", "offset_width", "endian", "offset_mode", "message_base", "message_end")},
        bank.upper(): {str(i): row for i, row in enumerate(match["records"])},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "PASS_EXACT_LAYOUT_EXTRACTED", "bank": bank.upper(), "records": count,
            "asset_sha256": actual, "layout_sha256": sha256(output.read_bytes()), "output": str(output)}


def selftest() -> dict[str, object]:
    count, base, end, table = 7, 0x100, 0x220, 0x20
    data = bytearray(end + 0x40)
    starts = [base, 0x124, 0x148, 0x170, 0x194, 0x1c0, 0x1e8]
    for i, start in enumerate(starts):
        stop = starts[i + 1] if i + 1 < count else end
        payload = bytes([i, 1, 2, 3]) + bytes(((i * 17 + j) & 0xff) for j in range(stop - start - 4))
        data[start:stop] = payload
    for i, start in enumerate(starts):
        struct.pack_into("<I", data, table + i * 4, start - base)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        asset, audit, output = root / "SYSTEM.MES", root / "audit.csv", root / "layout.json"
        asset.write_bytes(data)
        with audit.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["bank", "record", "source_record_sha256"])
            writer.writeheader()
            for i, start in enumerate(starts):
                stop = starts[i + 1] if i + 1 < count else end
                writer.writerow({"bank": "SYSTEM", "record": i, "source_record_sha256": sha256(data[start:stop])})
        result = extract(asset, audit, "SYSTEM", output, sha256(data), count, base, end, 0x80)
        doc = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
        bad = extract(asset, audit, "SYSTEM", root / "bad.json", "0" * 64, count, base, end, 0x80)
    passed = (result["status"] == "PASS_EXACT_LAYOUT_EXTRACTED" and doc.get("table", {}).get("table_offset") == table
              and doc.get("table", {}).get("offset_mode") == "relative" and bad["output_emitted"] is False)
    return {"status": "PASS" if passed else "FAIL", "exact": result, "negative_gate": bad}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("extract")
    run.add_argument("--asset", required=True, type=Path)
    run.add_argument("--audit", required=True, type=Path)
    run.add_argument("--bank", required=True, choices=("SYSTEM", "SYS14"))
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--expected-asset-sha256")
    run.add_argument("--record-count", type=int, default=229)
    run.add_argument("--message-base", type=lambda x: int(x, 0), default=0xE000)
    run.add_argument("--message-end", type=lambda x: int(x, 0), default=0x11000)
    run.add_argument("--search-limit", type=lambda x: int(x, 0), default=0x4000)
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else extract(
        args.asset, args.audit, args.bank, args.output, args.expected_asset_sha256,
        args.record_count, args.message_base, args.message_end, args.search_limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
