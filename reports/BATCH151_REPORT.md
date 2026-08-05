# Batch 151 — Exact B118 Character-Map Recovery

## Status

PASS_TOOLCHAIN_READY

## Completed

- Added `tools/recover_b118_character_maps.py`.
- Accepts `BATCH118_FONT_LIFECYCLE_MANIFEST.csv` or the historical B118 workbook.
- Locates the Font Lifecycle schema by headers rather than sheet name.
- Requires exactly one `SYSTEM` row and one `SYS14` row.
- Requires historical custom-character counts:
  - SYSTEM: 364
  - SYS14: 363
- Parses `character_map_json` and validates:
  - one Unicode character per key
  - slot range 0..447
  - unique character keys
  - unique slot assignments
  - no collision with declared reserved slots
  - exact entry count
  - optional font source SHA-256 format
- Emits separate normalized `SYSTEM_CHARACTER_MAP.json` and `SYS14_CHARACTER_MAP.json` only after every gate passes.
- Added positive and duplicate-slot rejection self-tests.
- Added `START_B151_RECOVER_CHARACTER_MAPS.cmd`.

## Historical grounding

File Library retains the exact B118 Font Lifecycle sidecar with two bank rows and the historical character maps. The retained sidecar manifest identifies 364 custom SYSTEM characters and 363 custom SYS14 characters.

## Safety

- No font file is committed.
- No glyph bitmap or game asset is committed.
- Character maps are not guessed or synthesized.
- Invalid, duplicate, out-of-range, reserved-slot-colliding or count-mismatched mappings fail closed.

## Next

Use the recovered maps with the existing fixed-layout extractor, candidate-record SHA recovery and exact MES assembler. Real asset production still requires filesystem-readable pristine SYSTEM/SYS14 plus the three B118 sidecars or the original workbook.
