# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 149 — PASS

The SYSTEM/SYS14 exact-recovery path no longer depends on a hand-authored fixed-allocation layout JSON.

## New components

- `tools/extract_mes_fixed_layout.py`
- `START_B149_EXTRACT_MES_LAYOUT.cmd`
- `reports/BATCH149_REPORT.md`

The extractor searches candidate MES offset-table interpretations across:

- 16-bit and 32-bit entries
- little-endian and big-endian values
- offsets relative to `0xE000` and absolute offsets

Structural plausibility is not sufficient. A layout is emitted only when all 229 source record slices reproduce the exact historical `source_record_sha256` values from `BATCH118_RECORD_AUDIT_458.csv`.

## Fixed-allocation output

For every record the generated layout contains:

- exact record offset
- exact allocation size
- original four-byte metadata
- source-record SHA-256

The final record is bounded by the historical `0x11000` message-region end, preserving its zero-filled remainder.

## Exact source gates

- SYSTEM source SHA-256:
  `943d6cf1fb996a416f90ad6e2bea2b147f4931623b480a1622cf200586ddd385`
- SYS14 source SHA-256:
  `69f618f86010c35f28d20efc40a9374a3fc99e594cc7b110ad91c4fa36ce1f5a`
- record coverage: 229/229 per bank
- message region: `0xE000..0x11000`

## Safety gates retained

- source whole-asset SHA-256
- complete and unique record-oracle coverage
- all 229 source-record SHA matches
- unique exact layout match
- candidate-record SHA-256
- SYSTEM/SYS14 whole-asset SHA-256
- 58-sector Expected Write
- MODE1/2352 EDC/ECC
- 2/2 re-extraction
- historical verification BIN/CUE SHA-256

No game bytes, font bytes, sidecar rows, or guessed record boundaries are committed.

## Active execution input

The real run requires filesystem-readable copies of:

- pristine `SYSTEM.MES`
- pristine `SYS14.MES`
- `BATCH118_RECORD_AUDIT_458.csv`
- `BATCH118_REVERSE_DECODE.csv`
- exact character-map JSON generated from the historical slot rules

File Library confirms the source hashes, 229-record relative layout model, final-record `0x11000` remainder rule, and exact record SHA oracles, but the indexed connector does not expose those files as mounted byte streams.

## Next

Extract the two exact layout JSON files, recover all 445 translated fixed-allocation records by candidate SHA, preserve the 13 control records byte-exactly, rebuild SYSTEM/SYS14, and run the whole-asset, raw-sector, EDC/ECC, re-extraction and historical BIN/CUE gates.
