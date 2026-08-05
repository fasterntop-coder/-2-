#!/usr/bin/env python3
"""Extract exact 16x16 4bpp glyph payloads from a user-owned game asset by SHA.

This avoids distributing a font file or embedding glyph bytes in the repository.
The scanner only writes a 128-byte glyph when its SHA-256 matches a configured
exact target and the match is unique.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

GLYPH_BYTES = 128


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scan(data: bytes, targets: dict[str, str], start: int, end: int, step: int) -> dict[str, list[int]]:
    wanted = {name: value.lower() for name, value in targets.items()}
    hits = {name: [] for name in wanted}
    for offset in range(start, max(start, end - GLYPH_BYTES + 1), step):
        digest = sha256(data[offset : offset + GLYPH_BYTES])
        for name, expected in wanted.items():
            if digest == expected:
                hits[name].append(offset)
    return hits


def extract(source: Path, targets_path: Path, output_dir: Path, start: int, end: int | None, step: int) -> dict[str, object]:
    data = source.read_bytes()
    targets_doc = json.loads(targets_path.read_text(encoding="utf-8"))
    targets = targets_doc.get("glyphs", targets_doc)
    if not isinstance(targets, dict) or not targets:
        raise ValueError("target JSON must contain a non-empty glyph map")
    scan_end = len(data) if end is None else min(end, len(data))
    if start < 0 or start >= scan_end:
        raise ValueError("invalid scan range")
    hits = scan(data, targets, start, scan_end, step)
    ambiguous = {name: offsets for name, offsets in hits.items() if len(offsets) != 1}
    if ambiguous:
        return {
            "status": "BLOCKED_NON_UNIQUE_OR_MISSING_GLYPH",
            "source": str(source),
            "source_sha256": sha256(data),
            "hits": {name: [hex(x) for x in offsets] for name, offsets in hits.items()},
            "output_emitted": False,
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, offsets in hits.items():
        offset = offsets[0]
        payload = data[offset : offset + GLYPH_BYTES]
        output = output_dir / f"{name}.4bpp"
        output.write_bytes(payload)
        outputs[name] = {"offset": hex(offset), "sha256": sha256(payload), "path": str(output)}
    return {
        "status": "PASS_EXACT_GLYPHS_EXTRACTED",
        "source": str(source),
        "source_sha256": sha256(data),
        "glyphs": outputs,
    }


def selftest() -> dict[str, object]:
    glyph_a = bytes((i * 7 + 3) & 255 for i in range(GLYPH_BYTES))
    glyph_b = bytes((i * 11 + 9) & 255 for i in range(GLYPH_BYTES))
    data = bytearray(b"\x00" * 4096)
    data[512 : 512 + GLYPH_BYTES] = glyph_a
    data[2048 : 2048 + GLYPH_BYTES] = glyph_b
    targets = {"높": sha256(glyph_a), "낮": sha256(glyph_b)}
    hits = scan(bytes(data), targets, 0, len(data), GLYPH_BYTES)
    return {
        "status": "PASS" if hits == {"높": [512], "낮": [2048]} else "FAIL",
        "hits": {name: [hex(x) for x in offsets] for name, offsets in hits.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("extract")
    run.add_argument("source", type=Path)
    run.add_argument("targets", type=Path)
    run.add_argument("output_dir", type=Path)
    run.add_argument("--start", type=lambda x: int(x, 0), default=0)
    run.add_argument("--end", type=lambda x: int(x, 0))
    run.add_argument("--step", type=lambda x: int(x, 0), default=GLYPH_BYTES)
    sub.add_parser("selftest")
    args = parser.parse_args()
    if args.command == "selftest":
        result = selftest()
    else:
        result = extract(args.source, args.targets, args.output_dir, args.start, args.end, args.step)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
