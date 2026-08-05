#!/usr/bin/env python3
"""Recover flattened Korean records into fixed MES allocations by SHA-256.

The B118 reverse-decode sidecar stores flattened Korean text while the historical
candidate record hashes preserve the exact FFFE line layout and zero padding.
This tool enumerates bounded line partitions from the original capacity vector,
encodes each candidate with a caller-supplied character map, preserves metadata,
FFFF termination and zero-filled allocation remainder, and accepts only an exact
candidate_record_sha256 match.

No game data or font bytes are bundled. Failure is closed: ambiguous, missing or
non-matching records are never emitted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

FFFE = 0xFFFE
FFFF = 0xFFFF
ZERO = 0x0000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def be16(tokens: Sequence[int]) -> bytes:
    return b"".join(struct.pack(">H", token) for token in tokens)


def parse_capacity(value: str) -> tuple[int, ...]:
    parts = tuple(int(x.strip()) for x in value.split("/") if x.strip())
    if not parts or any(x < 0 for x in parts):
        raise ValueError(f"invalid capacity vector: {value!r}")
    return parts


def line_lengths(total: int, capacities: Sequence[int]) -> Iterator[tuple[int, ...]]:
    """Yield all bounded line lengths whose sum is total.

    Empty display lines are valid. Enumeration is deterministic and prioritizes
    fuller earlier lines, matching the historical fixed-display convention.
    """
    if total < 0 or total > sum(capacities):
        return

    def walk(index: int, remaining: int, prefix: list[int]) -> Iterator[tuple[int, ...]]:
        if index == len(capacities):
            if remaining == 0:
                yield tuple(prefix)
            return
        rest_capacity = sum(capacities[index + 1 :])
        maximum = min(capacities[index], remaining)
        minimum = max(0, remaining - rest_capacity)
        for length in range(maximum, minimum - 1, -1):
            prefix.append(length)
            yield from walk(index + 1, remaining - length, prefix)
            prefix.pop()

    yield from walk(0, total, [])


def encode_text(text: str, character_map: dict[str, int]) -> list[int]:
    tokens: list[int] = []
    for char in text:
        if char not in character_map:
            raise KeyError(f"character is not allocated: {char!r}")
        token = int(character_map[char])
        if not 0 <= token < FFFE:
            raise ValueError(f"invalid glyph token {token} for {char!r}")
        tokens.append(token)
    return tokens


def build_record(metadata: bytes, glyphs: Sequence[int], lengths: Sequence[int], capacities: Sequence[int], allocation_size: int) -> bytes:
    if len(metadata) != 4:
        raise ValueError("record metadata must be exactly 4 bytes")
    if len(lengths) != len(capacities) or sum(lengths) != len(glyphs):
        raise ValueError("line partition does not cover glyph stream")
    tokens: list[int] = []
    cursor = 0
    for index, (used, capacity) in enumerate(zip(lengths, capacities)):
        if used > capacity:
            raise ValueError("line exceeds fixed capacity")
        tokens.extend(glyphs[cursor : cursor + used])
        tokens.extend([ZERO] * (capacity - used))
        cursor += used
        if index + 1 < len(capacities):
            tokens.append(FFFE)
    tokens.append(FFFF)
    record = metadata + be16(tokens)
    if len(record) > allocation_size:
        raise ValueError("compiled record exceeds original allocation")
    return record + bytes(allocation_size - len(record))


@dataclass(frozen=True)
class RecordRequest:
    bank: str
    record: int
    text: str
    capacities: tuple[int, ...]
    metadata: bytes
    allocation_size: int
    target_sha256: str


def recover_record(request: RecordRequest, character_map: dict[str, int]) -> dict[str, object]:
    glyphs = encode_text(request.text, character_map)
    matches: list[tuple[tuple[int, ...], bytes]] = []
    tested = 0
    for lengths in line_lengths(len(glyphs), request.capacities):
        tested += 1
        candidate = build_record(request.metadata, glyphs, lengths, request.capacities, request.allocation_size)
        if sha256(candidate) == request.target_sha256.lower():
            matches.append((lengths, candidate))
    if len(matches) != 1:
        return {
            "status": "BLOCKED_NO_UNIQUE_EXACT_RECORD" if not matches else "BLOCKED_AMBIGUOUS_EXACT_RECORD",
            "bank": request.bank,
            "record": request.record,
            "tested": tested,
            "exact_matches": len(matches),
            "output_emitted": False,
        }
    lengths, candidate = matches[0]
    return {
        "status": "PASS_EXACT_RECORD_RECOVERED",
        "bank": request.bank,
        "record": request.record,
        "tested": tested,
        "line_lengths": list(lengths),
        "zero_padding_tokens": sum(request.capacities) - len(glyphs),
        "sha256": sha256(candidate),
        "record_hex": candidate.hex(),
    }


def load_character_map(path: Path) -> dict[str, int]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    raw = doc.get("character_map", doc)
    if not isinstance(raw, dict):
        raise ValueError("character map JSON must be an object")
    return {str(k): int(v) for k, v in raw.items()}


def load_requests(reverse_csv: Path, audit_csv: Path, layout_json: Path) -> list[RecordRequest]:
    layout = json.loads(layout_json.read_text(encoding="utf-8"))
    reverse: dict[tuple[str, int], str] = {}
    with reverse_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            bank = str(row.get("bank", "")).strip().upper()
            record = int(row["record"])
            expected = str(row.get("expected", row.get("decoded_korean", row.get("decoded", ""))))
            decoded = str(row.get("decoded", expected))
            status = str(row.get("status", "PASS")).upper()
            if expected != decoded or status != "PASS":
                raise ValueError(f"reverse-decode gate failed at {bank}:{record}")
            reverse[(bank, record)] = decoded
    requests: list[RecordRequest] = []
    with audit_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            bank = str(row["bank"]).strip().upper()
            record = int(row["record"])
            key = (bank, record)
            if key not in reverse:
                continue  # control records remain byte-exact from source
            item = layout[bank][str(record)]
            requests.append(
                RecordRequest(
                    bank=bank,
                    record=record,
                    text=reverse[key],
                    capacities=parse_capacity(row["capacity"]),
                    metadata=bytes.fromhex(item["metadata_hex"]),
                    allocation_size=int(item["allocation_size"]),
                    target_sha256=str(row["candidate_record_sha256"]).lower(),
                )
            )
    return requests


def recover_all(reverse_csv: Path, audit_csv: Path, layout_json: Path, map_json: Path, output: Path) -> dict[str, object]:
    character_map = load_character_map(map_json)
    requests = load_requests(reverse_csv, audit_csv, layout_json)
    results = [recover_record(request, character_map) for request in requests]
    failed = [row for row in results if row["status"] != "PASS_EXACT_RECORD_RECOVERED"]
    result = {
        "status": "PASS_ALL_EXACT_RECORDS_RECOVERED" if not failed else "BLOCKED_RECORD_SHA_MISMATCH",
        "records": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def selftest() -> dict[str, object]:
    cmap = {char: index + 1 for index, char in enumerate("가나다라마바사아자차카타파하")}
    metadata = bytes.fromhex("01020304")
    text = "가나다라마바사"
    capacities = (4, 0, 5)
    expected_lengths = (3, 0, 4)
    allocation = 4 + 2 * (sum(capacities) + len(capacities) - 1 + 1) + 8
    target = build_record(metadata, encode_text(text, cmap), expected_lengths, capacities, allocation)
    request = RecordRequest("SYSTEM", 112, text, capacities, metadata, allocation, sha256(target))
    recovered = recover_record(request, cmap)

    # Negative gate: a wrong oracle must never emit bytes.
    blocked = recover_record(RecordRequest("SYSTEM", 113, text, capacities, metadata, allocation, "0" * 64), cmap)
    passed = (
        recovered["status"] == "PASS_EXACT_RECORD_RECOVERED"
        and recovered["line_lengths"] == list(expected_lengths)
        and recovered["zero_padding_tokens"] == 2
        and blocked["status"] == "BLOCKED_NO_UNIQUE_EXACT_RECORD"
        and blocked["output_emitted"] is False
    )
    return {"status": "PASS" if passed else "FAIL", "exact": recovered, "negative_gate": blocked}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("recover")
    run.add_argument("--reverse", required=True, type=Path)
    run.add_argument("--audit", required=True, type=Path)
    run.add_argument("--layout", required=True, type=Path)
    run.add_argument("--character-map", required=True, type=Path)
    run.add_argument("--output", type=Path, default=Path("output/B158_RECORD_RECOVERY.json"))
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else recover_all(args.reverse, args.audit, args.layout, args.character_map, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
