#!/usr/bin/env python3
"""Run the exact B140 PBOOK_BT 高/低 -> 높/낮 recovery pipeline.

Inputs are a user-owned Korean SYSTEM/MES asset containing the exact glyphs and
the pristine PBOOK_BT.CG source. The runner extracts glyphs by SHA, creates a
resolved temporary job, executes the palette-transfer search and preserves the
SHA-gated result JSON.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXTRACTOR = HERE / "extract_glyph_by_sha.py"
SEARCH = HERE / "pbook_palette_transfer_search.py"
GLYPH_TARGETS = ROOT / "manifests" / "PBOOK_BT_GLYPH_TARGETS.json"
JOB_TEMPLATE = ROOT / "jobs" / "PBOOK_BT_HEIGHT_LOW.json"


def run(command: list[str]) -> dict[str, object]:
    proc = subprocess.run(command, text=True, capture_output=True)
    if proc.stdout:
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON output: {proc.stdout}") from exc
    else:
        result = {"status": "NO_OUTPUT"}
    if proc.returncode not in (0, 2):
        raise RuntimeError(proc.stderr or proc.stdout)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True, type=Path, help="Korean SYSTEM/MES asset containing exact glyphs")
    parser.add_argument("--pbook", required=True, type=Path, help="Pristine PBOOK_BT.CG")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "B140")
    parser.add_argument("--font-start", type=lambda x: int(x, 0), default=0)
    parser.add_argument("--font-end", type=lambda x: int(x, 0))
    parser.add_argument("--max-candidates", type=int)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    glyph_dir = output_dir / "glyphs"
    output_dir.mkdir(parents=True, exist_ok=True)

    extract_cmd = [
        sys.executable,
        str(EXTRACTOR),
        "extract",
        str(args.system.resolve()),
        str(GLYPH_TARGETS),
        str(glyph_dir),
        "--start",
        hex(args.font_start),
    ]
    if args.font_end is not None:
        extract_cmd += ["--end", hex(args.font_end)]
    extract_result = run(extract_cmd)
    (output_dir / "GLYPH_EXTRACTION_RESULT.json").write_text(
        json.dumps(extract_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not str(extract_result.get("status", "")).startswith("PASS"):
        print(json.dumps({"status": "BLOCKED_GLYPH_EXTRACTION", "detail": extract_result}, ensure_ascii=False, indent=2))
        return 2

    template = json.loads(JOB_TEMPLATE.read_text(encoding="utf-8"))
    template["source_path"] = str(args.pbook.resolve())
    template["output_path"] = str((output_dir / "PBOOK_BT_B140_EXACT.CG").resolve())
    for region in template["regions"]:
        region["mask_path"] = str((glyph_dir / f"{region['korean']}.4bpp").resolve())
    resolved_job = output_dir / "PBOOK_BT_HEIGHT_LOW_RESOLVED.json"
    resolved_job.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")

    search_cmd = [sys.executable, str(SEARCH), "search", str(resolved_job)]
    if args.max_candidates is not None:
        search_cmd += ["--max-candidates", str(args.max_candidates)]
    search_result = run(search_cmd)
    result = {
        "status": search_result.get("status"),
        "glyph_extraction": extract_result,
        "palette_search": search_result,
    }
    (output_dir / "B140_RUN_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result["status"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
