# Batch327 — PSP↔Saturn Disc 1 MES bridge

Source PSP archive: `SAKURA2 MES.zip`

- SHA-256: `7d1e0795b327841a6cf7ad264ccf3c41f602ebe5bd1f65b64b7dd08d266eb9b5`
- MES files: 399
- Total uncompressed MES bytes: 7,461,782
- PSP/root-table layout: 382
- Full Saturn-style table at `0xE000`: 17

## Disc 1 story bridge

Compared against `ST2_DISC1_STORY_EXTRACT_MANIFEST.json`.

- Saturn story MES entries: 109
- PSP filename overlap: 109/109
- Comparable non-placeholder record counts: 107
- Exact record-count matches: 107/107
- Record-count mismatches: 0
- Exact Saturn-size minus PSP-size delta of `0xE000` (57,344 bytes): 77 files
- Two Saturn Disc 1 placeholder entries have no comparable Saturn message count and are excluded from the 107/107 gate.

Examples:

- `EV02001.MES`: Saturn 3 records / PSP 3 records; size delta `0xE000`
- `EV27001.MES`: Saturn 4 / PSP 4; size delta `0xE000`
- `EV27002.MES`: Saturn 21 / PSP 21; size delta `0xE000`

Observed PSP text-token endian is little-endian. `0xFFFE` is the line-break control and `0xFFFF` is the record terminator. No Hangul/token mapping was guessed or applied.

## Battle/system bridge

Compared against `BATCH111_BATTLE_BANK_COVERAGE_55.csv`.

- Saturn banks: 55
- PSP overlap: 55/55
- Exact record-count matches: 55/55
- Byte-identical PSP↔Saturn files by size and SHA-256: 16

Byte-identical files:

`SYS06.MES`, `SYS28.MES`, `SYS30.MES`, `SYS32.MES`, `SYS35.MES`, `SYS38.MES`, `SYS39.MES`, `SYS40.MES`, `SYS41.MES`, `SYS42.MES`, `SYS43.MES`, `SYS44.MES`, `SYS48.MES`, `SYS50.MES`, `SYSTEM.MES`, `SYS14.MES`.

## Proven reuse boundary

The PSP MES binaries must not be copied wholesale into Saturn files. Their text token endian/layout differs and most PSP story MES omit the Saturn per-file `0xE000` font-bank region.

The proven reusable boundary is record identity/order and metadata/control structure. Once `FNT4B.CMP` (and, if necessary, `SAKURA2.ELF`) yields the PSP token→Hangul mapping, the PSP Korean text can be decoded by record index and re-encoded into the existing Saturn per-file font/token pipeline without guessing bytes.

Tool: `tools/analyze_psp_sakura2_mes_bridge.py`
