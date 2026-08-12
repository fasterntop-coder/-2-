#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

MSG_START = 0xE000
MSG_END = 0x11000
FONT_SLOTS = 448
GLYPH_BYTES = 128
FONT_INDEX = 1
FONT_SIZE = 14
DRAW_X = 1
DRAW_Y = -4

SPECS: dict[str, dict[str, Any]] = {
    "EV00002.MES": {
        "source_sha256": "07e4f2272b0cc5755f89e1b1c50bb641ac9da8e0c600ca8d8a989f8f392c5708",
        "lba": 247457,
        "record_updates": {
            0: "좋아, 해냈다……\n하지만 저 마조기병은\n분명 「협시」였어……"
        },
        "reason": {
            0: "脇侍 is canonicalized as 협시 in the verified battle/system banks; the PSP bridge independently resolves it as 협시."
        },
    },
    "EV00060.MES": {
        "source_sha256": "f26295cffa37706af3792d194c39384e634565029ab2e0c5348153a8966c641d",
        "lba": 247407,
        "record_updates": {
            3: "역시 아이젠클라이드!",
            7: "역시 아이젠클라이드!",
        },
        "reason": {
            3: "Project canonical proper noun for アイゼンクライト is 아이젠클라이드.",
            7: "Project canonical proper noun for アイゼンクライト is 아이젠클라이드.",
        },
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_mes(data: bytes) -> tuple[list[int], list[dict[str, Any]]]:
    if len(data) < MSG_END:
        raise ValueError("MES shorter than fixed message region")
    count = int.from_bytes(data[MSG_START:MSG_START + 4], "big")
    offsets = [
        int.from_bytes(data[MSG_START + 4 + i * 4:MSG_START + 8 + i * 4], "big")
        for i in range(count)
    ]
    if not offsets or offsets[0] < 4 + count * 4:
        raise ValueError("invalid first record offset")
    if any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("record offsets are not strictly increasing")
    records: list[dict[str, Any]] = []
    for i, rel_start in enumerate(offsets):
        rel_end = offsets[i + 1] if i + 1 < count else MSG_END - MSG_START
        start = MSG_START + rel_start
        end = MSG_START + rel_end
        tokens: list[int] = []
        terminated = False
        for p in range(start + 4, end, 2):
            token = int.from_bytes(data[p:p + 2], "big")
            tokens.append(token)
            if token == 0xFFFF:
                terminated = True
                break
        if not terminated:
            raise ValueError(f"unterminated record {i}")
        records.append({
            "index": i,
            "start": start,
            "end": end,
            "metadata": data[start:start + 4],
            "tokens": tokens,
            "bytes": data[start:end],
        })
    return offsets, records


def load_rows(path: Path, filename: str) -> dict[int, dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if "ledger" in obj:
        rows = obj["ledger"]
    else:
        rows = [r for v in obj.get("files", {}).values() for r in v.get("records", [])]
    return {int(r["record"]): r for r in rows if r.get("file") == filename}


def render_glyph(ch: str, font_path: Path) -> bytes:
    font = ImageFont.truetype(str(font_path), FONT_SIZE, index=FONT_INDEX)
    im = Image.new("L", (16, 16), 0)
    ImageDraw.Draw(im).text((DRAW_X, DRAW_Y), ch, font=font, fill=255)
    values = list(im.getdata())
    q = [min(15, (v + 8) // 17) for v in values]
    return bytes((q[i] << 4) | q[i + 1] for i in range(0, 256, 2))


def build_char_map(data: bytes, rows: dict[int, dict[str, Any]]) -> tuple[dict[int, str], dict[str, int], list[int]]:
    _, records = parse_mes(data)
    token_to_char: dict[int, str] = {}
    char_to_token: dict[str, int] = {}
    aligned: list[int] = []
    for record in records:
        row = rows.get(record["index"])
        if not row or row.get("status") == "CONTROL_PRESERVE":
            continue
        text = row.get("translation_ko")
        if text is None:
            continue
        expected = [0xFFFE if ch == "\n" else ch for ch in text]
        visible = record["tokens"][:-1]
        if len(expected) != len(visible):
            continue
        for ch, token in zip(expected, visible):
            if ch == 0xFFFE:
                if token != 0xFFFE:
                    raise ValueError(f"linebreak mismatch record {record['index']}")
                continue
            if token >= FONT_SLOTS:
                raise ValueError(f"non-font token in aligned record {record['index']}: {token:#06x}")
            if token in token_to_char and token_to_char[token] != ch:
                raise ValueError(f"token {token} has conflicting characters")
            if ch in char_to_token and char_to_token[ch] != token:
                raise ValueError(f"character {ch!r} has conflicting font slots")
            token_to_char[token] = ch
            char_to_token[ch] = token
        aligned.append(record["index"])
    return token_to_char, char_to_token, aligned


def encode_text(text: str, char_to_token: dict[str, int]) -> list[int]:
    out: list[int] = []
    for ch in text:
        if ch == "\n":
            out.append(0xFFFE)
        else:
            if ch not in char_to_token:
                raise KeyError(ch)
            out.append(char_to_token[ch])
    out.append(0xFFFF)
    return out


def reverse_decode(tokens: list[int], token_to_char: dict[int, str]) -> str:
    out: list[str] = []
    for token in tokens:
        if token == 0xFFFF:
            break
        if token == 0xFFFE:
            out.append("\n")
        elif token < FONT_SLOTS:
            out.append(token_to_char.get(token, f"<{token:04X}>"))
        else:
            out.append(f"<{token:04X}>")
    return "".join(out)


def build_one(filename: str, base_path: Path, ledger_path: Path, font_path: Path, out_path: Path) -> dict[str, Any]:
    spec = SPECS[filename]
    raw = base_path.read_bytes()
    if sha256(raw) != spec["source_sha256"]:
        raise ValueError(f"{filename}: source SHA mismatch")
    rows = load_rows(ledger_path, filename)
    token_to_char, char_to_token, aligned = build_char_map(raw, rows)

    hangul = [(slot, ch) for slot, ch in token_to_char.items() if "가" <= ch <= "힣"]
    raster_bad = [
        (slot, ch) for slot, ch in hangul
        if raw[slot * GLYPH_BYTES:(slot + 1) * GLYPH_BYTES] != render_glyph(ch, font_path)
    ]
    if raster_bad:
        raise ValueError(f"{filename}: exact local-font raster proof failed: {raster_bad[:5]}")

    offsets, before = parse_mes(raw)
    used_slots = {t for r in before for t in r["tokens"] if t < FONT_SLOTS}
    buf = bytearray(raw)
    new_slots: dict[str, int] = {}
    required = set("".join(spec["record_updates"].values())) - set(char_to_token) - {"\n"}
    for ch in sorted(required):
        if not ("가" <= ch <= "힣"):
            raise ValueError(f"{filename}: unmapped non-Hangul character {ch!r}")
        free = next((s for s in range(1, FONT_SLOTS) if s not in used_slots and s not in token_to_char), None)
        if free is None:
            raise ValueError(f"{filename}: no free font slot")
        char_to_token[ch] = free
        token_to_char[free] = ch
        used_slots.add(free)
        new_slots[ch] = free
        buf[free * GLYPH_BYTES:(free + 1) * GLYPH_BYTES] = render_glyph(ch, font_path)

    changed_records: list[int] = []
    for record_index, text in spec["record_updates"].items():
        rec = before[record_index]
        tokens = encode_text(text, char_to_token)
        payload = rec["metadata"] + b"".join(t.to_bytes(2, "big") for t in tokens)
        capacity = rec["end"] - rec["start"]
        if len(payload) > capacity:
            raise ValueError(f"{filename} record {record_index}: overflow {len(payload)}/{capacity}")
        payload += bytes(capacity - len(payload))
        buf[rec["start"]:rec["end"]] = payload
        changed_records.append(record_index)

    out = bytes(buf)
    out_offsets, after = parse_mes(out)
    if offsets != out_offsets:
        raise ValueError(f"{filename}: record offset table changed")
    table_bytes = 4 + len(offsets) * 4
    if raw[MSG_START:MSG_START + table_bytes] != out[MSG_START:MSG_START + table_bytes]:
        raise ValueError(f"{filename}: message table bytes changed")
    if raw[MSG_END:] != out[MSG_END:]:
        raise ValueError(f"{filename}: execution tail changed")
    for a, b in zip(before, after):
        if a["metadata"] != b["metadata"]:
            raise ValueError(f"{filename}: metadata changed in record {a['index']}")
        if a["index"] not in changed_records and a["bytes"] != b["bytes"]:
            raise ValueError(f"{filename}: untouched record changed: {a['index']}")

    allowed_font_bytes: set[int] = set()
    for slot in new_slots.values():
        allowed_font_bytes.update(range(slot * GLYPH_BYTES, (slot + 1) * GLYPH_BYTES))
    actual_font_diff = {i for i, (a, b) in enumerate(zip(raw[:MSG_START], out[:MSG_START])) if a != b}
    if not actual_font_diff.issubset(allowed_font_bytes):
        raise ValueError(f"{filename}: font bank changed outside allocated slots")

    decoded: dict[str, str] = {}
    for record_index, expected in spec["record_updates"].items():
        got = reverse_decode(after[record_index]["tokens"], token_to_char)
        if got != expected:
            raise ValueError(f"{filename}: reverse decode mismatch in record {record_index}: {got!r}")
        decoded[str(record_index)] = got

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out)
    return {
        "iso_path": f"SAKURA2/{filename}",
        "lba": spec["lba"],
        "size": len(out),
        "source_sha256": sha256(raw),
        "replacement_sha256": sha256(out),
        "aligned_records_for_map": len(aligned),
        "existing_hangul_glyphs_exact_raster_match": f"{len(hangul)}/{len(hangul)}",
        "new_font_slots": new_slots,
        "changed_records": changed_records,
        "reverse_decoded": decoded,
        "message_offset_table_byte_exact": True,
        "all_record_metadata_byte_exact": True,
        "execution_tail_byte_exact": True,
        "untouched_records_byte_exact": True,
        "font_changes_limited_to_new_slots": True,
        "reasons": {str(k): v for k, v in spec["reason"].items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Batch329 PSP-guided high-confidence Disc1 EV MES corrections")
    ap.add_argument("--ev00002-base", type=Path, required=True)
    ap.add_argument("--ev00060-base", type=Path, required=True)
    ap.add_argument("--ev00002-ledger", type=Path, required=True)
    ap.add_argument("--ev00060-ledger", type=Path, required=True)
    ap.add_argument("--font", type=Path, required=True, help="Exact NotoSansCJK-Bold TTC used by the current Event MES lineage")
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "EV00002.MES": build_one(
            "EV00002.MES", args.ev00002_base, args.ev00002_ledger, args.font,
            args.out_dir / "SAKURA2" / "EV00002.MES"
        ),
        "EV00060.MES": build_one(
            "EV00060.MES", args.ev00060_base, args.ev00060_ledger, args.font,
            args.out_dir / "SAKURA2" / "EV00060.MES"
        ),
    }
    report = {
        "format": "ST2-CD1-BATCH329-PSP-QUALITY-REPLACEMENTS-v1",
        "batch": 329,
        "status": "PASS_ACTUAL_REPLACEMENT_MES_2_FILES_3_RECORDS",
        "scope": {"replacement_files": 2, "changed_records": 3},
        "files": files,
        "font_proof": {
            "family": "Noto Sans CJK Bold",
            "size_px": FONT_SIZE,
            "draw_xy": [DRAW_X, DRAW_Y],
            "format": "16x16 4bpp high-nibble-first grayscale",
            "quantization": "min(15,(alpha+8)//17)",
        },
        "guessed_bytes": 0,
        "parent_disc_write_performed": False,
    }
    manifest = args.out_dir / "BATCH329_PSP_QUALITY_REPLACEMENTS.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
