#!/usr/bin/env python3
"""Recover and validate B118 Reverse Decode / Record Audit sidecars.

Accepts either loose CSV exports or the historical workbook. Nothing is trusted
by filename alone: exact row counts, bank splits, record coverage and required
SHA/text fields are validated before normalized CSVs are emitted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

REVERSE_NAME = "BATCH118_REVERSE_DECODE.csv"
AUDIT_NAME = "BATCH118_RECORD_AUDIT_458.csv"
REVERSE_ROWS = 445
AUDIT_ROWS = 458
REVERSE_SPLIT = {"SYSTEM": 222, "SYS14": 223}
AUDIT_SPLIT = {"SYSTEM": 229, "SYS14": 229}
REVERSE_REQUIRED = {"bank", "record", "decoded_korean"}
AUDIT_REQUIRED = {"bank", "record", "source_record_sha256", "candidate_record_sha256"}
SHA_FIELDS = {"source_record_sha256", "candidate_record_sha256"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024 * 1024): h.update(block)
    return h.hexdigest()


def norm(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return [{norm(k): norm(v) for k, v in row.items()} for row in csv.DictReader(f)]
        except UnicodeDecodeError: continue
    raise ValueError(f"cannot decode CSV: {path}")


def workbook_rows(path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for workbook extraction") from exc
    wb = load_workbook(path, read_only=True, data_only=True)
    found: dict[str, list[dict[str, str]]] = {}
    for ws in wb.worksheets:
        values = ws.iter_rows(values_only=True)
        try: header = [norm(x) for x in next(values)]
        except StopIteration: continue
        rows = [{header[i]: norm(v) for i, v in enumerate(row) if i < len(header)} for row in values]
        lowered = {h.lower() for h in header}
        if AUDIT_REQUIRED.issubset(lowered): found["audit"] = rows
        elif REVERSE_REQUIRED.issubset(lowered): found["reverse"] = rows
    if "reverse" not in found or "audit" not in found:
        raise ValueError("required Reverse Decode / Record Audit sheets not found")
    return found["reverse"], found["audit"]


def find_inputs(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    reverse = next(root.rglob(REVERSE_NAME), None); audit = next(root.rglob(AUDIT_NAME), None)
    if reverse and audit:
        return read_csv(reverse), read_csv(audit), {"mode": "loose_csv", "reverse": str(reverse), "audit": str(audit), "reverse_sha256": sha256(reverse), "audit_sha256": sha256(audit)}
    for book in root.rglob("*.xlsx"):
        try:
            r, a = workbook_rows(book)
            return r, a, {"mode": "workbook", "workbook": str(book), "workbook_sha256": sha256(book)}
        except Exception: continue
    raise FileNotFoundError("B118 sidecar CSVs or workbook not found")


def validate(rows: list[dict[str, str]], expected_rows: int, split: dict[str, int], required: set[str], kind: str) -> list[dict[str, str]]:
    if len(rows) != expected_rows: raise ValueError(f"{kind}: rows {len(rows)} != {expected_rows}")
    normalized = [{k.lower(): v for k, v in row.items()} for row in rows]
    if not normalized or not required.issubset(normalized[0]): raise ValueError(f"{kind}: required columns missing")
    counts = Counter(row["bank"] for row in normalized)
    if dict(counts) != split: raise ValueError(f"{kind}: bank split {dict(counts)} != {split}")
    seen: set[tuple[str, int]] = set()
    for row in normalized:
        key = (row["bank"], int(row["record"]))
        if key in seen: raise ValueError(f"{kind}: duplicate {key}")
        seen.add(key)
        if not 0 <= key[1] <= 228: raise ValueError(f"{kind}: record out of range {key}")
        for field in required:
            if not row.get(field, ""): raise ValueError(f"{kind}: blank {field} at {key}")
        for field in SHA_FIELDS & required:
            value = row[field].lower()
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value): raise ValueError(f"{kind}: invalid {field} at {key}")
    return normalized


def write_csv(path: Path, rows: list[dict[str, str]]) -> str:
    fields = list(rows[0]); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
    return sha256(path)


def recover(root: Path, output: Path) -> dict[str, object]:
    reverse, audit, source = find_inputs(root)
    reverse = validate(reverse, REVERSE_ROWS, REVERSE_SPLIT, REVERSE_REQUIRED, "reverse")
    audit = validate(audit, AUDIT_ROWS, AUDIT_SPLIT, AUDIT_REQUIRED, "audit")
    if not {(r["bank"], int(r["record"])) for r in reverse}.issubset({(r["bank"], int(r["record"])) for r in audit}):
        raise ValueError("reverse rows are not a subset of audited records")
    output.mkdir(parents=True, exist_ok=True); rpath, apath = output / REVERSE_NAME, output / AUDIT_NAME
    result = {"status": "PASS_B118_SIDECARS_RECOVERED", "source": source, "reverse_rows": len(reverse), "audit_rows": len(audit), "reverse_sha256": write_csv(rpath, reverse), "audit_sha256": write_csv(apath, audit), "reverse_path": str(rpath), "audit_path": str(apath)}
    (output / "B118_SIDECAR_RECOVERY_RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def selftest() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); out = root / "out"
        def emit(path: Path, rows: int, sys_count: int, reverse: bool) -> None:
            fields = ["bank", "record", "decoded_korean"] if reverse else ["bank", "record", "source_record_sha256", "candidate_record_sha256"]
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
                for i in range(rows):
                    bank = "SYSTEM" if i < sys_count else "SYS14"; rec = i if i < sys_count else i - sys_count; row = {"bank": bank, "record": rec}
                    if reverse: row["decoded_korean"] = f"문장{i}"
                    else: row.update(source_record_sha256=f"{i:064x}"[-64:], candidate_record_sha256=f"{i+1:064x}"[-64:])
                    w.writerow(row)
        emit(root / REVERSE_NAME, 445, 222, True); emit(root / AUDIT_NAME, 458, 229, False)
        result = recover(root, out); return {"status": "PASS" if result["status"].startswith("PASS") else "FAIL"}


def main() -> int:
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recover"); r.add_argument("root", type=Path); r.add_argument("--output-dir", type=Path, default=Path("output/B118_SIDECARS")); sub.add_parser("selftest"); args = p.parse_args()
    result = selftest() if args.cmd == "selftest" else recover(args.root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if str(result["status"]).startswith("PASS") else 2

if __name__ == "__main__": raise SystemExit(main())
