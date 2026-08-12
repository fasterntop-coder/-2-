#!/usr/bin/env python3
"""Analyze PSP Sakura Taisen 2 MES files against Saturn Disc 1 manifests.

No byte guessing or text decoding is performed. The tool only proves structural
relationships from observed counts, offsets, metadata and SHA-256 values.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import zipfile

FONT_BANK = 0xE000
MAX_RECORDS = 2048


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_pointer_table(data: bytes, base: int) -> dict | None:
    if len(data) < base + 8:
        return None
    count = int.from_bytes(data[base:base + 4], "big")
    if not (1 <= count <= MAX_RECORDS):
        return None
    table_end = base + 4 + count * 4
    if table_end > len(data):
        return None
    raw = [int.from_bytes(data[base + 4 + i * 4:base + 8 + i * 4], "big") for i in range(count)]
    region_size = len(data) - base
    candidates: list[tuple[str, list[int]]] = []
    if raw and all(0 <= x < region_size for x in raw):
        candidates.append(("RELATIVE", raw))
    if raw and all(base <= x < len(data) for x in raw):
        candidates.append(("ABSOLUTE", [x - base for x in raw]))
    for offset_mode, rel in candidates:
        if rel[0] < 4 + count * 4:
            continue
        if any(a >= b for a, b in zip(rel, rel[1:])):
            continue
        if rel[-1] >= region_size:
            continue
        recs = []
        controls = {"FFFE": 0, "FFFF": 0}
        for idx, start in enumerate(rel):
            end = rel[idx + 1] if idx + 1 < count else region_size
            if end <= start + 4:
                return None
            abs_start = base + start
            abs_end = base + end
            rec = data[abs_start:abs_end]
            metadata = rec[:4]
            tokens = []
            terminated = False
            for p in range(4, len(rec) - 1, 2):
                tok = int.from_bytes(rec[p:p + 2], "little")
                if tok == 0xFFFF:
                    controls["FFFF"] += 1
                    terminated = True
                    break
                if tok == 0xFFFE:
                    controls["FFFE"] += 1
                tokens.append(tok)
            recs.append({
                "index": idx,
                "offset": start,
                "metadata_hex": metadata.hex(),
                "token_count_before_terminator": len(tokens),
                "line_breaks": sum(t == 0xFFFE for t in tokens),
                "terminated": terminated,
            })
        return {
            "base": base,
            "count": count,
            "offset_mode": offset_mode,
            "offsets": rel,
            "records": recs,
            "controls": controls,
        }
    return None


def parse_mes(data: bytes) -> dict:
    root = parse_pointer_table(data, 0)
    full = parse_pointer_table(data, FONT_BANK)
    if root is not None:
        layout = "ROOT_TABLE_FONTLESS_OR_PSP"
        parsed = root
    elif full is not None:
        layout = "FULL_SATURN_STYLE_0xE000"
        parsed = full
    else:
        return {"layout": "UNKNOWN", "record_count": None, "table_base": None}
    return {
        "layout": layout,
        "record_count": parsed["count"],
        "table_base": parsed["base"],
        "offset_mode": parsed["offset_mode"],
        "first_metadata_hex": parsed["records"][0]["metadata_hex"],
        "line_breaks": parsed["controls"]["FFFE"],
        "terminated_records": parsed["controls"]["FFFF"],
        "all_records_terminated": parsed["controls"]["FFFF"] == parsed["count"],
    }


def load_story_manifest(path: Path) -> list[dict]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, list):
        rows = obj
    else:
        rows = next(
            v for v in obj.values()
            if isinstance(v, list) and (not v or isinstance(v[0], dict))
        )
    return [r for r in rows if str(r.get("path", "")).upper().endswith(".MES")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--psp-zip", required=True, type=Path)
    ap.add_argument("--saturn-story-manifest", required=True, type=Path)
    ap.add_argument("--saturn-battle-csv", type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    archive_bytes = args.psp_zip.read_bytes()
    inventory: dict[str, dict] = {}
    with zipfile.ZipFile(args.psp_zip) as zf:
        names = [n for n in zf.namelist() if n.upper().endswith(".MES") and not n.endswith("/")]
        for n in names:
            data = zf.read(n)
            base = os.path.basename(n).upper()
            p = parse_mes(data)
            inventory[base] = {
                "archive_path": n,
                "size": len(data),
                "sha256": sha256(data),
                **p,
            }

    story = load_story_manifest(args.saturn_story_manifest)
    story_rows = []
    comparable = matched = mismatched = missing = 0
    exact_e000_delta = 0
    for s in story:
        name = os.path.basename(s["path"]).upper()
        p = inventory.get(name)
        sat_count = s.get("message_count")
        row = {
            "file": name,
            "saturn_path": s.get("path"),
            "saturn_size": s.get("size"),
            "saturn_sha256": s.get("sha256"),
            "saturn_record_count": sat_count,
            "psp_present": p is not None,
            "psp_size": p.get("size") if p else None,
            "psp_sha256": p.get("sha256") if p else None,
            "psp_layout": p.get("layout") if p else None,
            "psp_record_count": p.get("record_count") if p else None,
            "record_count_match": None,
            "size_delta_saturn_minus_psp": None,
        }
        if p is None:
            missing += 1
        else:
            if s.get("size") is not None:
                delta = int(s["size"]) - int(p["size"])
                row["size_delta_saturn_minus_psp"] = delta
                if delta == FONT_BANK:
                    exact_e000_delta += 1
            if sat_count is not None:
                comparable += 1
                row["record_count_match"] = int(sat_count) == int(p["record_count"])
                if row["record_count_match"]:
                    matched += 1
                else:
                    mismatched += 1
        story_rows.append(row)

    battle_summary = None
    battle_rows = []
    if args.saturn_battle_csv:
        with args.saturn_battle_csv.open(encoding="utf-8-sig", newline="") as f:
            sat_battle = list(csv.DictReader(f))
        b_overlap = b_count_match = b_sha_identical = 0
        for s in sat_battle:
            name = os.path.basename(s["path"]).upper()
            p = inventory.get(name)
            row = {
                "file": name,
                "saturn_path": s["path"],
                "saturn_size": int(s["size"]),
                "saturn_sha256": s["sha256"],
                "saturn_record_count": int(s["records"]),
                "psp_present": p is not None,
                "psp_layout": p.get("layout") if p else None,
                "psp_size": p.get("size") if p else None,
                "psp_sha256": p.get("sha256") if p else None,
                "record_count_match": False,
                "byte_identical": False,
            }
            if p:
                b_overlap += 1
                row["record_count_match"] = p.get("record_count") == int(s["records"])
                b_count_match += int(row["record_count_match"])
                row["byte_identical"] = p["size"] == int(s["size"]) and p["sha256"] == s["sha256"]
                b_sha_identical += int(row["byte_identical"])
            battle_rows.append(row)
        battle_summary = {
            "saturn_banks": len(sat_battle),
            "psp_overlap": b_overlap,
            "record_count_matches": b_count_match,
            "byte_identical": b_sha_identical,
            "byte_identical_files": [r["file"] for r in battle_rows if r["byte_identical"]],
        }

    layout_counts: dict[str, int] = {}
    for p in inventory.values():
        layout_counts[p["layout"]] = layout_counts.get(p["layout"], 0) + 1

    summary = {
        "schema": "st2-psp-saturn-mes-bridge-v1",
        "psp_archive": {
            "path": args.psp_zip.name,
            "sha256": sha256(archive_bytes),
            "mes_files": len(inventory),
            "total_uncompressed_mes_bytes": sum(x["size"] for x in inventory.values()),
            "layout_counts": layout_counts,
        },
        "saturn_story_bridge": {
            "manifest_mes_files": len(story),
            "psp_overlap": len(story) - missing,
            "comparable_non_placeholder_counts": comparable,
            "record_count_matches": matched,
            "record_count_mismatches": mismatched,
            "exact_0xE000_size_delta_files": exact_e000_delta,
            "placeholder_or_unknown_saturn_counts": len(story) - comparable,
        },
        "saturn_battle_bridge": battle_summary,
        "proof_points": {
            "psp_text_token_endian": "little",
            "line_break_token": "0xFFFE",
            "record_end_token": "0xFFFF",
            "font_bank_bytes": FONT_BANK,
            "guessed_text_mapping_applied": False,
        },
        "story_rows": story_rows,
        "battle_rows": battle_rows,
        "psp_inventory": inventory,
    }

    json_path = args.out_dir / "PSP_SATURN_MES_BRIDGE.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = args.out_dir / "PSP_SATURN_STORY_BRIDGE.csv"
    fields = list(story_rows[0].keys()) if story_rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(story_rows)

    inv_path = args.out_dir / "PSP_MES_INVENTORY.csv"
    inv_rows = [{"file": n, **p} for n, p in sorted(inventory.items())]
    inv_fields = list(inv_rows[0].keys()) if inv_rows else []
    with inv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=inv_fields)
        w.writeheader(); w.writerows(inv_rows)

    print(json.dumps({
        "output_json": str(json_path),
        "output_story_csv": str(csv_path),
        "output_inventory_csv": str(inv_path),
        "summary": {
            "mes_files": len(inventory),
            "layouts": layout_counts,
            "story_overlap": len(story)-missing,
            "story_count_matches": f"{matched}/{comparable}",
            "battle": battle_summary,
        }
    }, ensure_ascii=False, indent=2))
    return 0 if mismatched == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
