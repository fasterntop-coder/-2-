# Batch 167 — SK1304 exact production promotion

## Status

`PASS_SK1304_EXACT_PRODUCTION_PROMOTION`

## Promoted asset

- ISO path: `SAKURA1/SK1304.BIN`
- LBA: `46008`
- size: `44,464`
- source SHA-256: `591e9b23b035b3bb5786043318695c865d771d22aa8f53fbcc433359b04418f2`
- replacement SHA-256: `ff6e9b29a6ba76f8ee706f55041a9f83bb6246f24061efbfd00d41d042a54722`
- records reviewed: `149/149`
- translated records: `146`
- preserved control records: `47, 113, 126`
- FFFD control records: `112, 125`
- confirmed translation reuse: `47`
- new translations: `99`
- font slots: `236 used + 15 preserved / 252`, `1 remaining`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- header/pointer/control structure: preserved and reparsed equal

## Production scope

- exact assets: `39`
- story assets: `36`
- movie assets: `3`
- subtitle events: `33`

## Added components

- `manifests/SK1304_FINAL_EXACT_TARGET.json`
- `START_B167_PRODUCTION_WITH_SK1304.cmd`
- `.github/workflows/batch167-production.yml`

## Safety gates retained

The existing production engine rejects all writes unless the pristine Disc SHA-256, per-asset source Expected Write, replacement size/SHA-256, MODE1/2352 EDC/ECC regeneration, changed-sector accounting, and exact whole-asset re-extraction gates pass. No inferred payload bytes are accepted or committed.
