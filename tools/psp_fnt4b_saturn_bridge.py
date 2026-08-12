#!/usr/bin/env python3
"""Exact bridge tools for the PSP Sakura Taisen 2 Korean patch assets.

Grounded in the uploaded ULJM-05109 SAKURA2.ELF implementation:
- FNT4B.CMP uses the game's type-0/parameter-0 LZ decoder.
- FNT4B decompressed font is 4-byte header + 3488 x 32x32 4bpp glyphs.
- SJIS codes are converted to JIS; JIS rows 0x30..0x48 are repurposed as
  the 2350 KS X 1001 (EUC-KR B0A1..C8FE) Hangul syllables in sequence.
- PSP MES count/offset tables are big-endian, while 16-bit text tokens are
  stored little-endian. FFFE is line break and FFFF is terminator.

This script deliberately does not write Saturn game files. It produces exact
reference/mapping assets and an optional 16x16 raster master for later guarded
Saturn compilation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

FNT4B_EXPECTED_SHA256 = "c441d4dd7e488839a9c8b559c3f0ec32393efb7a194ef22260b47cd826018572"
ELF_EXPECTED_SHA256 = "5eeecfd632776385e1301833d1fe57668f22b4232ee3e686952d4795eff5babd"
DECOMPRESSED_SIZE = 0x1B4004
ATLAS_HEADER_SIZE = 4
GLYPH_W = 32
GLYPH_H = 32
GLYPH_BPP = 4
GLYPH_BYTES = 512
ATLAS_GLYPHS = 3488
ATLAS_COLUMNS = 32
HANGUL_FIRST_INDEX = 492
HANGUL_COUNT = 2350
HANGUL_LAST_INDEX = HANGUL_FIRST_INDEX + HANGUL_COUNT - 1

CUSTOM_PUNCT = {
    0x81AC: "⁉",
    0x81B8: "‼",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def decompress_fnt4b_cmp(blob: bytes) -> bytes:
    """Exact ELF 0x0893EADC -> type0 decoder path used by supplied FNT4B.CMP."""
    if len(blob) < 4:
        raise ValueError("CMP is too short")
    b0 = blob[0]
    ctype = (b0 & 0x70) >> 4
    param = b0 & 0x0F
    compact_header = bool(b0 & 0x80)
    if (ctype, param, compact_header) != (0, 0, True):
        raise ValueError(
            f"unsupported/unproven CMP variant type={ctype} param={param} compact={compact_header}"
        )
    out_size = int.from_bytes(blob[:4], "big") & 0xFFFFFF
    if out_size != DECOMPRESSED_SIZE:
        raise ValueError(f"unexpected FNT4B output size {out_size:#x}")

    shift = 12
    length_base = 3
    distance_mask = (1 << shift) - 1
    src = 4
    out = bytearray(out_size)
    dst = 0
    flags = 0x7F80

    while dst < out_size:
        flags = (flags << 1) & 0xFFFF
        if flags == 0xFF00:
            if src >= len(blob):
                raise ValueError("CMP truncated while reading flag byte")
            flags = (blob[src] << 8) | 0xFF
            src += 1

        if flags & 0x8000:
            if src >= len(blob):
                raise ValueError("CMP truncated while reading literal")
            out[dst] = blob[src]
            dst += 1
            src += 1
        else:
            if src + 1 >= len(blob):
                raise ValueError("CMP truncated while reading back-reference")
            token = (blob[src] << 8) | blob[src + 1]
            src += 2
            distance = token & distance_mask
            run = length_base + (token >> shift)
            for _ in range(run):
                if dst >= out_size:
                    break
                back = dst - distance
                out[dst] = out[back] if back >= 0 else 0
                dst += 1

    if src != len(blob):
        raise ValueError(f"CMP decoder did not consume entire input: {src}/{len(blob)}")
    if len(out) != ATLAS_HEADER_SIZE + ATLAS_GLYPHS * GLYPH_BYTES:
        raise ValueError("decompressed font geometry does not close exactly")
    return bytes(out)


def valid_sjis(code: int) -> bool:
    hi = (code >> 8) & 0xFF
    lo = code & 0xFF
    return ((0x81 <= hi <= 0x9F) or (0xE0 <= hi <= 0xEA)) and 0x40 <= lo <= 0xFC and lo != 0x7F


def sjis_to_jis(code: int) -> int:
    """Exact arithmetic from ELF 0x089464EC."""
    hi = (code >> 8) & 0xFF
    lo = code & 0xFF
    if not valid_sjis(code):
        raise ValueError(f"not a valid two-byte Shift-JIS code: {code:04X}")
    if hi < 0xA0:
        row = hi * 2 - (0xE1 if lo < 0x9F else 0xE0)
    else:
        row = hi * 2 - (0x161 if lo < 0x9F else 0x160)
    if lo < 0x7F:
        col = lo - 0x1F
    elif lo < 0x9F:
        col = lo - 0x20
    else:
        col = lo - 0x7E
    return ((row & 0xFF) << 8) | (col & 0xFF)


def build_jis_to_sjis() -> dict[int, int]:
    out: dict[int, int] = {}
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xEB)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F:
                continue
            code = (hi << 8) | lo
            try:
                jis = sjis_to_jis(code)
            except ValueError:
                continue
            out.setdefault(jis, code)
    return out


def hangul_info_from_sjis(code: int) -> tuple[str, int, int] | None:
    if not valid_sjis(code):
        return None
    jis = sjis_to_jis(code)
    row, col = (jis >> 8) & 0xFF, jis & 0xFF
    if not (0x30 <= row <= 0x48 and 0x21 <= col <= 0x7E):
        return None
    k = (row - 0x30) * 94 + (col - 0x21)
    if not 0 <= k < HANGUL_COUNT:
        return None
    euc = bytes([0xB0 + k // 94, 0xA1 + k % 94])
    ch = euc.decode("euc_kr")
    return ch, HANGUL_FIRST_INDEX + k, k


def decode_psp_token(code: int) -> tuple[str, str]:
    if code == 0xFFFE:
        return "\n", "linebreak"
    if code == 0xFFFF:
        return "", "end"
    if code in CUSTOM_PUNCT:
        return CUSTOM_PUNCT[code], "custom_punct"
    hi = hangul_info_from_sjis(code)
    if hi is not None:
        return hi[0], "hangul"
    if not valid_sjis(code):
        return f"<CTRL:{code:04X}>", "control"
    try:
        return code.to_bytes(2, "big").decode("cp932"), "sjis"
    except UnicodeDecodeError:
        return f"<SJIS:{code:04X}>", "unknown"


def parse_psp_mes(blob: bytes) -> tuple[int, int, list[int]]:
    """Return (table_base, count, absolute_record_offsets)."""
    for base in (0, 0xE000):
        if len(blob) < base + 8:
            continue
        count = int.from_bytes(blob[base:base + 4], "big")
        if not 0 < count <= 2048:
            continue
        table_end = base + 4 + count * 4
        if table_end > len(blob):
            continue
        raw = [int.from_bytes(blob[base + 4 + 4*i:base + 8 + 4*i], "big") for i in range(count)]
        if not all(a < b for a, b in zip(raw, raw[1:])):
            continue
        abs_offsets = [x + base if x < base else x for x in raw]
        if abs_offsets[0] < table_end or abs_offsets[-1] >= len(blob):
            continue
        return base, count, abs_offsets
    raise ValueError("PSP MES offset table not found at 0 or 0xE000")


def decode_record(blob: bytes) -> dict:
    if len(blob) < 6:
        raise ValueError("record too short")
    metadata = blob[:4]
    tokens: list[int] = []
    text: list[str] = []
    kinds: list[str] = []
    terminated = False
    for p in range(4, len(blob) - 1, 2):
        token = int.from_bytes(blob[p:p+2], "little")
        tokens.append(token)
        ch, kind = decode_psp_token(token)
        kinds.append(kind)
        if kind == "end":
            terminated = True
            break
        text.append(ch)
    return {
        "metadata_hex": metadata.hex(),
        "text": "".join(text),
        "tokens_hex": " ".join(f"{x:04X}" for x in tokens),
        "terminated": terminated,
        "contains_control": any(x in {"control", "unknown"} for x in kinds),
        "hangul_tokens": sum(x == "hangul" for x in kinds),
        "custom_punct_tokens": sum(x == "custom_punct" for x in kinds),
    }


def glyph_pixels_32(font: bytes, atlas_index: int) -> list[list[int]]:
    if not 0 <= atlas_index < ATLAS_GLYPHS:
        raise ValueError("atlas index out of range")
    col = atlas_index % ATLAS_COLUMNS
    row_base = (atlas_index // ATLAS_COLUMNS) * GLYPH_H
    pixels: list[list[int]] = []
    for y in range(GLYPH_H):
        pos = ATLAS_HEADER_SIZE + (row_base + y) * (ATLAS_COLUMNS * 16) + col * 16
        row: list[int] = []
        for b in font[pos:pos+16]:
            row.extend(((b >> 4) & 0xF, b & 0xF))
        pixels.append(row)
    return pixels


def convert_saturn16_slot(font: bytes, atlas_index: int) -> bytes:
    """Conservative 32->16 candidate: PSP shape, Saturn palette 0/1/13.

    2x2 average preserves the PSP antialiased outline shape. Pixel average >=8
    becomes body index 13; >=2.5 becomes edge index 1; otherwise transparent 0.
    This is a candidate raster only, not an authoritative game write.
    """
    src = glyph_pixels_32(font, atlas_index)
    dst = [[0] * 16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            avg = (
                src[y*2][x*2] + src[y*2][x*2+1] +
                src[y*2+1][x*2] + src[y*2+1][x*2+1]
            ) / 4.0
            if avg >= 8.0:
                dst[y][x] = 13
            elif avg >= 2.5:
                dst[y][x] = 1
    packed = bytearray()
    for row in dst:
        for x in range(0, 16, 2):
            packed.append((row[x] << 4) | row[x+1])
    if len(packed) != 128:
        raise AssertionError("Saturn slot must be 128 bytes")
    return bytes(packed)


def write_ks_map(path: Path) -> None:
    inv = build_jis_to_sjis()
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ks_index", "unicode", "euc_kr", "jis", "sjis_token", "psp_atlas_index"])
        for k in range(HANGUL_COUNT):
            euc = bytes([0xB0 + k // 94, 0xA1 + k % 94])
            ch = euc.decode("euc_kr")
            row = 0x30 + k // 94
            col = 0x21 + k % 94
            jis = (row << 8) | col
            sjis = inv.get(jis)
            if sjis is None:
                raise ValueError(f"no SJIS inverse for JIS {jis:04X}")
            w.writerow([k, ch, euc.hex().upper(), f"{jis:04X}", f"{sjis:04X}", HANGUL_FIRST_INDEX + k])


def decode_mes_zip(zip_path: Path, out_jsonl: Path) -> dict:
    totals = {"files": 0, "records": 0, "hangul_tokens": 0, "custom_punct_tokens": 0, "control_records": 0}
    with zipfile.ZipFile(zip_path) as zf, out_jsonl.open("w", encoding="utf-8") as out:
        names = sorted(n for n in zf.namelist() if n.upper().endswith(".MES"))
        for name in names:
            blob = zf.read(name)
            base, count, offsets = parse_psp_mes(blob)
            totals["files"] += 1
            for i, start in enumerate(offsets):
                end = offsets[i+1] if i+1 < count else len(blob)
                rec = decode_record(blob[start:end])
                row = {
                    "file": Path(name).name,
                    "record": i,
                    "table_base": base,
                    **rec,
                }
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                totals["records"] += 1
                totals["hangul_tokens"] += rec["hangul_tokens"]
                totals["custom_punct_tokens"] += rec["custom_punct_tokens"]
                totals["control_records"] += int(rec["contains_control"])
    return totals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fnt4b", type=Path, required=True)
    ap.add_argument("--elf", type=Path)
    ap.add_argument("--mes-zip", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    cmp_blob = args.fnt4b.read_bytes()
    cmp_sha = sha256_bytes(cmp_blob)
    if cmp_sha != FNT4B_EXPECTED_SHA256:
        raise SystemExit(f"FNT4B SHA mismatch: {cmp_sha}")
    font = decompress_fnt4b_cmp(cmp_blob)
    font_sha = sha256_bytes(font)
    (args.out / "FNT4B.DEC").write_bytes(font)

    elf_sha = None
    if args.elf:
        elf_sha = sha256_file(args.elf)
        if elf_sha != ELF_EXPECTED_SHA256:
            raise SystemExit(f"ELF SHA mismatch: {elf_sha}")

    write_ks_map(args.out / "PSP_KSX1001_FONT_MAP.csv")

    sat16 = bytearray()
    for k in range(HANGUL_COUNT):
        sat16 += convert_saturn16_slot(font, HANGUL_FIRST_INDEX + k)
    (args.out / "PSP_KSX1001_SATURN16_CANDIDATE.bin").write_bytes(sat16)

    mes_totals = None
    if args.mes_zip:
        mes_totals = decode_mes_zip(args.mes_zip, args.out / "PSP_MES_KO_DECODED.jsonl")

    manifest = {
        "format": "st2-psp-fnt4b-saturn-bridge-v1",
        "source": {
            "fnt4b_sha256": cmp_sha,
            "elf_sha256": elf_sha,
        },
        "cmp": {
            "decoder_entry_elf_va": "0x0893EADC",
            "load_init_entry_elf_va": "0x08946204",
            "type": 0,
            "parameter": 0,
            "distance_bits": 12,
            "length_base": 3,
            "decompressed_size": len(font),
            "decompressed_sha256": font_sha,
        },
        "font": {
            "header_bytes": ATLAS_HEADER_SIZE,
            "atlas_glyphs": ATLAS_GLYPHS,
            "geometry": "32x32",
            "bpp": GLYPH_BPP,
            "bytes_per_glyph": GLYPH_BYTES,
            "atlas_columns": ATLAS_COLUMNS,
            "atlas_rows": ATLAS_GLYPHS // ATLAS_COLUMNS,
            "hangul_first_atlas_index": HANGUL_FIRST_INDEX,
            "hangul_last_atlas_index": HANGUL_LAST_INDEX,
            "hangul_count": HANGUL_COUNT,
            "hangul_mapping": "KS X 1001 EUC-KR B0A1..C8FE sequentially in JIS 0x3021..0x487E",
            "sjis_to_jis_entry_elf_va": "0x089464EC",
            "glyph_render_entry_elf_va": "0x089465A0",
            "glyph_copy_entry_elf_va": "0x08947210",
        },
        "saturn16_candidate": {
            "size": len(sat16),
            "sha256": sha256_bytes(bytes(sat16)),
            "slot_bytes": 128,
            "palette_indices": {"transparent": 0, "edge": 1, "body": 13},
            "status": "RASTER_CANDIDATE_ONLY_NOT_GAME_WRITE",
        },
        "mes": mes_totals,
        "guessed_bytes": 0,
    }
    (args.out / "PSP_FNT4B_BRIDGE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
