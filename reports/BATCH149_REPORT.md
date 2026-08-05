# Batch 149 — Exact MES Fixed-Allocation Layout Extraction

## Status

PASS_TOOLCHAIN_COMPLETE_RUNTIME_INPUT_PENDING

## Completed

- Added `tools/extract_mes_fixed_layout.py`.
- Added `START_B149_EXTRACT_MES_LAYOUT.cmd`.
- Removed the need for a hand-authored SYSTEM/SYS14 layout JSON.
- The extractor discovers candidate 16-bit/32-bit, little-endian/big-endian, relative/absolute offset tables.
- A layout is emitted only when all 229 source record slices match the historical `source_record_sha256` values from `BATCH118_RECORD_AUDIT_458.csv`.
- The final record is bounded by the historical `0x11000` message-region end, preserving its zero-filled remainder.
- Per-record output includes exact offset, allocation size, four-byte metadata, and source record SHA-256.
- Wrong source asset SHA, incomplete oracle coverage, zero matches, and ambiguous matches fail closed without output.

## Exact source gates

- SYSTEM source SHA-256: `943d6cf1fb996a416f90ad6e2bea2b147f4931623b480a1622cf200586ddd385`
- SYS14 source SHA-256: `69f618f86010c35f28d20efc40a9374a3fc99e594cc7b110ad91c4fa36ce1f5a`
- Record count: 229 per bank
- Message base: `0xE000`
- Message end: `0x11000`

## Safety

No game bytes are committed. No record boundary is accepted from structural plausibility alone. Every record boundary must reproduce the retained source-record SHA oracle for all 229 records.

## Next execution

Run the launcher with pristine `SYSTEM.MES`, pristine `SYS14.MES`, and the exact `BATCH118_RECORD_AUDIT_458.csv`. Feed the two generated layout JSON files into `recover_fixed_record_layout.py` together with the normalized Reverse Decode sidecar and exact character map. Accept resulting assets only after all candidate-record, whole-asset, Expected Write, MODE1/2352 EDC/ECC, re-extraction, and historical BIN/CUE SHA gates pass.
