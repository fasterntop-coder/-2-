# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 147 — PASS

The B118 sidecar recovery path now accepts and validates the actual historical
File Library schemas instead of only the Batch 146 synthetic test schema.

## Corrected component

- `tools/recover_b118_sidecars.py`
- `reports/BATCH147_REPORT.md`
- `START_B146_RECOVER_B118_SIDECARS.cmd` remains the execution entry point.

## Historical Reverse Decode gate

Accepted source columns include:

- `bank`
- `record`
- `type`
- `expected`
- `decoded`
- `status`

Required validation:

- 445 rows
- SYSTEM 222 / SYS14 223
- unique bank/record keys in range 0..228
- nonblank expected and decoded text
- exact `expected == decoded`
- `status == PASS` when present
- strict subset of the 458 audited records

A canonical `decoded_korean` field is emitted for downstream compilers without
removing the historical fields.

## Historical Record Audit gate

Required validation:

- 458 rows
- SYSTEM 229 / SYS14 229
- complete 0..228 record coverage for each bank
- unique bank/record keys
- valid hexadecimal 64-character source record SHA-256
- valid hexadecimal 64-character candidate record SHA-256

## Exact downstream gates retained

- SYSTEM target SHA-256:
  `aff08f718bb8186c7162601f76b927dfa516c21139f60fc6d3cf27f8a8a84a58`
- SYS14 target SHA-256:
  `06597ddf3d34f0463e611f796146bb1e80d7e32df1f59925481669969840b92d`
- combined verification BIN SHA-256:
  `4343b8845f7f9cd4725de085e3a779c7c77185c0e6043d99b5d226335b69f5cf`
- combined verification CUE SHA-256:
  `eb09178d66b35beed0a84fe2b93c4740c6bf8046c2aeb3dd1c375131dd5b4453`
- Expected Write, MODE1/2352 EDC/ECC and 2/2 re-extraction remain mandatory.

## CI

GitHub Actions run 17: SUCCESS.

All compilation, PBOOK recovery, exact patch roundtrip, checkpoint mosaic,
legacy apply parser and historical-header B118 sidecar recovery tests passed.

## Active execution input

The corrected tool must be run where the following exact File Library CSVs are
mounted as real files:

- `BATCH118_REVERSE_DECODE.csv`
- `BATCH118_RECORD_AUDIT_458.csv`

The current connector exposes their indexed contents and IDs but not a mounted
filesystem path usable by the compiler. No game bytes or sidecar rows were
guessed or reconstructed from hashes.

## Next

Mount or otherwise expose the two exact CSV byte streams to the runtime, run
sidecar normalization, then execute the SYSTEM/SYS14 exact compiler. Accept no
output unless both whole-asset SHA gates, all record SHA gates, the 58-sector
Expected Write/EDC/ECC gate, re-extraction and historical verification BIN/CUE
SHA gates pass.
