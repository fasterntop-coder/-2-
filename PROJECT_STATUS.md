# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 151 — PASS

The exact SYSTEM/SYS14 rebuild path can now recover the historical character-to-slot maps directly from the B118 Font Lifecycle CSV or workbook.

## New components

- `tools/recover_b118_character_maps.py`
- `START_B151_RECOVER_CHARACTER_MAPS.cmd`
- `reports/BATCH151_REPORT.md`

## Exact character-map gates

- exactly one SYSTEM row and one SYS14 row
- SYSTEM custom characters: 364
- SYS14 custom characters: 363
- slot domain: 0..447
- one Unicode character per key
- unique character keys and unique slot values
- no collision with declared reserved slots
- optional font-source SHA-256 syntax validation

Separate normalized bank maps are emitted only after every gate passes.

## Existing exact rebuild chain

1. `tools/recover_b118_sidecars.py`
2. `tools/recover_b118_character_maps.py`
3. `tools/extract_mes_fixed_layout.py`
4. `tools/recover_fixed_record_layout.py`
5. `tools/assemble_exact_mes_assets.py`
6. B124 whole-asset SHA gates
7. 58-sector Expected Write
8. MODE1/2352 EDC/ECC
9. SYSTEM/SYS14 2/2 re-extraction
10. historical BIN/CUE SHA gates

## Safety

- No game, font or glyph bitmap bytes committed.
- No guessed characters, slots, record boundaries or sector bytes accepted.
- Invalid or ambiguous inputs fail closed.

## Active execution inputs

Real SYSTEM/SYS14 output requires filesystem-readable copies of:

- pristine `SYSTEM.MES` — SHA-256 `943d6cf1fb996a416f90ad6e2bea2b147f4931623b480a1622cf200586ddd385`
- pristine `SYS14.MES` — SHA-256 `69f618f86010c35f28d20efc40a9374a3fc99e594cc7b110ad91c4fa36ce1f5a`
- `BATCH118_REVERSE_DECODE.csv`
- `BATCH118_RECORD_AUDIT_458.csv`
- `BATCH118_FONT_LIFECYCLE_MANIFEST.csv`

The historical B118 workbook may replace all three CSV sidecars.
