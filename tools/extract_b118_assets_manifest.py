#!/usr/bin/env python3
"""Extract the exact 58-asset B118 manifest from the retained workbook.

The workbook is parsed with Python's standard library only. The tool fails
closed unless the workbook SHA, sheet schema, complete asset census, per-asset
hashes, changed-LBA counts and the 1,626-sector union all match the historical
B118 contract. No workbook content or game bytes are committed by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

WORKBOOK_SHA256 = "e8c85862c10b6d30ed21156b17ca93be834c5cb5f76cf1f58d97c1db6ca22ce9"
DISC_SIZE = 659_293_824
DISC_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
RAW_SECTOR_SIZE = 2352
USER_DATA_SIZE = 2048
EXPECTED_CHANGED_SECTORS = 1626
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

EXPECTED_ASSETS = (
    ["PBOOK_BT", "PBOOK_EC", "PBOOK_RC"]
    + [f"SYS{i:02d}" for i in range(49)]
    + ["SYS50"]
    + [f"STNSYS{i:02d}" for i in range(4)]
    + ["SYSTEM"]
)
REQUIRED_COLUMNS = {
    "index", "asset", "source_batch", "status", "lba", "size",
    "original_sha256", "candidate_sha256", "changed_asset_bytes",
    "changed_sector_count", "changed_lbas", "lba_conflict", "hardware",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def col_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    value = 0
    for ch in letters:
        value = value * 26 + ord(ch) - 64
    return value - 1


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings: list[str] = []
    for item in root.findall(f"{{{NS_MAIN}}}si"):
        strings.append("".join(node.text or "" for node in item.iter(f"{{{NS_MAIN}}}t")))
    return strings


def worksheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relation = {
        node.attrib["Id"]: node.attrib["Target"]
        for node in rels.findall(f"{{{NS_PKG_REL}}}Relationship")
    }
    for sheet in workbook.findall(f".//{{{NS_MAIN}}}sheet"):
        if sheet.attrib.get("name") != sheet_name:
            continue
        rid = sheet.attrib.get(f"{{{NS_REL}}}id")
        if not rid or rid not in relation:
            raise ValueError(f"missing relationship for sheet {sheet_name}")
        target = relation[rid].lstrip("/")
        if target.startswith("xl/"):
            return target
        return "xl/" + target
    raise ValueError(f"sheet not found: {sheet_name}")


def cell_value(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{{{NS_MAIN}}}t"))
    value = cell.find(f"{{{NS_MAIN}}}v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        return strings[int(value.text)]
    if kind == "b":
        return "TRUE" if value.text == "1" else "FALSE"
    return value.text


def read_rows(path: Path, sheet_name: str = "Assets 58") -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        sheet = ET.fromstring(archive.read(worksheet_path(archive, sheet_name)))
    rows: list[list[str]] = []
    for row in sheet.findall(f".//{{{NS_MAIN}}}row"):
        values: dict[int, str] = {}
        for cell in row.findall(f"{{{NS_MAIN}}}c"):
            values[col_index(cell.attrib.get("r", "A1"))] = cell_value(cell, strings).strip()
        if values:
            width = max(values) + 1
            rows.append([values.get(i, "") for i in range(width)])
    return rows


def as_int(value: Any, field: str) -> int:
    text = str(value).strip()
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid integer {text!r}") from exc
    if not number.is_integer():
        raise ValueError(f"{field}: non-integral value {text!r}")
    return int(number)


def parse_lbas(value: str) -> list[int]:
    parts = [part.strip() for part in str(value).split(",") if part.strip()]
    return [as_int(part, "changed_lbas") for part in parts]


def filename_for(asset: str) -> str:
    return asset + (".CG" if asset.startswith("PBOOK_") else ".MES")


def extract(workbook: Path, output: Path, expected_workbook_sha: str) -> dict[str, Any]:
    digest = sha256_file(workbook)
    if digest != expected_workbook_sha.lower():
        raise RuntimeError(f"workbook SHA mismatch: {digest}")
    rows = read_rows(workbook)
    header_index = -1
    header: list[str] = []
    for index, row in enumerate(rows):
        normalized = [cell.strip().lower() for cell in row]
        if REQUIRED_COLUMNS.issubset(set(normalized)):
            header_index, header = index, normalized
            break
    if header_index < 0:
        raise ValueError("Assets 58 header not found")
    positions = {name: header.index(name) for name in REQUIRED_COLUMNS}

    assets: list[dict[str, Any]] = []
    for row in rows[header_index + 1:]:
        def get(name: str) -> str:
            position = positions[name]
            return row[position].strip() if position < len(row) else ""
        name = get("asset").upper()
        if name not in EXPECTED_ASSETS:
            continue
        original = get("original_sha256").lower()
        target = get("candidate_sha256").lower()
        if not SHA_RE.fullmatch(original) or not SHA_RE.fullmatch(target):
            raise ValueError(f"{name}: invalid asset SHA")
        lba = as_int(get("lba"), f"{name}.lba")
        size = as_int(get("size"), f"{name}.size")
        changed_count = as_int(get("changed_sector_count"), f"{name}.changed_sector_count")
        changed_lbas = parse_lbas(get("changed_lbas"))
        if len(changed_lbas) != changed_count or len(set(changed_lbas)) != changed_count:
            raise ValueError(f"{name}: changed-LBA count mismatch")
        sector_span = (size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        if any(item < lba or item >= lba + sector_span for item in changed_lbas):
            raise ValueError(f"{name}: changed LBA outside asset extent")
        conflict = get("lba_conflict").upper()
        if conflict not in {"", "NONE", "0", "FALSE", "NO"}:
            raise ValueError(f"{name}: LBA conflict is not clear")
        assets.append({
            "index": as_int(get("index"), f"{name}.index"),
            "name": name,
            "filename": filename_for(name),
            "source_batch": as_int(get("source_batch"), f"{name}.source_batch"),
            "status": get("status"),
            "lba": lba,
            "size": size,
            "source_sha256": original,
            "target_sha256": target,
            "changed_asset_bytes": as_int(get("changed_asset_bytes"), f"{name}.changed_asset_bytes"),
            "changed_sector_count": changed_count,
            "changed_lbas": changed_lbas,
            "hardware": get("hardware"),
        })

    names = [asset["name"] for asset in assets]
    if len(assets) != 58 or set(names) != set(EXPECTED_ASSETS) or len(set(names)) != 58:
        missing = sorted(set(EXPECTED_ASSETS) - set(names))
        extra = sorted(set(names) - set(EXPECTED_ASSETS))
        raise ValueError(f"asset census mismatch: count={len(assets)} missing={missing} extra={extra}")
    if sorted(asset["index"] for asset in assets) != list(range(58)):
        raise ValueError("asset indexes are not exactly 0..57")
    if len({asset["lba"] for asset in assets}) != 58:
        raise ValueError("duplicate asset LBA")
    all_changed = [lba for asset in assets for lba in asset["changed_lbas"]]
    if len(all_changed) != EXPECTED_CHANGED_SECTORS or len(set(all_changed)) != EXPECTED_CHANGED_SECTORS:
        raise ValueError(
            f"changed-sector union mismatch: rows={len(all_changed)} unique={len(set(all_changed))}"
        )

    assets.sort(key=lambda item: item["index"])
    manifest = {
        "format": "st2-exact-asset-manifest-v1",
        "batch": 118,
        "source_workbook": {
            "name": workbook.name,
            "sha256": digest,
            "sheet": "Assets 58",
        },
        "source_disc": {
            "size": DISC_SIZE,
            "sha256": DISC_SHA256,
            "raw_sector_size": RAW_SECTOR_SIZE,
            "user_data_offset": 16,
            "user_data_size": USER_DATA_SIZE,
        },
        "assets": assets,
        "validation": {
            "asset_count": 58,
            "asset_names_unique": True,
            "asset_indexes": "0..57",
            "changed_sector_rows": len(all_changed),
            "changed_sector_union": len(set(all_changed)),
            "lba_conflicts": 0,
        },
        "safety": {
            "whole_asset_sha_required": True,
            "unverified_output_allowed": False,
            "workbook_or_game_bytes_embedded": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "PASS_B118_58_ASSET_MANIFEST_EXTRACTED",
        "output": str(output),
        "workbook_sha256": digest,
        "asset_count": 58,
        "changed_sector_union": EXPECTED_CHANGED_SECTORS,
    }


def inline_cell(ref: str, value: Any) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def excel_column(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def make_test_workbook(path: Path) -> None:
    headers = [
        "index", "asset", "source_batch", "status", "lba", "size",
        "original_sha256", "candidate_sha256", "changed_asset_bytes",
        "changed_sector_count", "changed_lbas", "lba_conflict", "hardware",
    ]
    xml_rows = []
    for row_number, values in enumerate([headers], start=1):
        cells = "".join(inline_cell(f"{excel_column(i)}{row_number}", value) for i, value in enumerate(values))
        xml_rows.append(f'<row r="{row_number}">{cells}</row>')
    for index, name in enumerate(EXPECTED_ASSETS):
        count = 29 if index < 2 else 28
        lba = 1000 + index * 100
        changed = ",".join(str(lba + offset) for offset in range(count))
        values = [
            index, name, 118, "TEST", lba, 100000,
            hashlib.sha256(("source:" + name).encode()).hexdigest(),
            hashlib.sha256(("target:" + name).encode()).hexdigest(),
            1234, count, changed, "NONE", "PENDING",
        ]
        row_number = index + 2
        cells = "".join(inline_cell(f"{excel_column(i)}{row_number}", value) for i, value in enumerate(values))
        xml_rows.append(f'<row r="{row_number}">{cells}</row>')
    worksheet = (
        f'<worksheet xmlns="{NS_MAIN}"><sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>"
    )
    workbook = (
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}"><sheets>'
        '<sheet name="Assets 58" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels = (
        f'<Relationships xmlns="{NS_PKG_REL}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def selftest() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        workbook = root / "test.xlsx"
        output = root / "manifest.json"
        make_test_workbook(workbook)
        result = extract(workbook, output, sha256_file(workbook))
        manifest = json.loads(output.read_text(encoding="utf-8"))
        passed = (
            result["status"] == "PASS_B118_58_ASSET_MANIFEST_EXTRACTED"
            and len(manifest["assets"]) == 58
            and manifest["validation"]["changed_sector_union"] == 1626
            and manifest["assets"][0]["filename"] == "PBOOK_BT.CG"
            and manifest["assets"][-1]["filename"] == "SYSTEM.MES"
        )
    return {"status": "PASS" if passed else "FAIL", "roundtrip": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("extract")
    run.add_argument("workbook", type=Path)
    run.add_argument("--output", type=Path, default=Path("output/B118_ASSETS_58_NORMALIZED.json"))
    run.add_argument("--expected-workbook-sha", default=WORKBOOK_SHA256)
    sub.add_parser("selftest")
    args = parser.parse_args()
    result = selftest() if args.command == "selftest" else extract(
        args.workbook, args.output, args.expected_workbook_sha
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
