# Batch 163 — SK0501 exact production promotion

## Status

`PASS_SK0501_EXACT_PRODUCTION_PROMOTION`

## Promoted asset

- ISO path: `SAKURA1/SK0501.BIN`
- LBA: `45704`
- size: `246748`
- source SHA-256: `8ba6f9332c7dd84b39aa72cb20b98df417d1395db2ec696fd95a9824d879544f`
- replacement SHA-256: `6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743`
- records reviewed: `1559/1559`
- translated records: `1558`
- control records preserved: `1`
- FFFD special controls preserved: `15/15`
- font slots: `712 used + 15 preserved / 892`, `165 remaining`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- validation: `PASS_OFFLINE`

## Production scope

The exact executable production manifest now contains:

- story assets: `33`
- movie assets: `3`
- total assets: `36`
- subtitle events: `33`

## Added components

- `manifests/SK0501_FINAL_EXACT_TARGET.json`
- `START_B163_PRODUCTION_WITH_SK0403_SK0504_SK0501.cmd`
- `.github/workflows/batch163-production.yml`

## Safety gates retained

- pristine Disc 1 full SHA-256 gate
- per-asset source SHA-256 Expected Write gate
- exact replacement size and SHA-256 gate
- overlap and duplicate-path rejection
- MODE1/2352 EDC, ECC-P and ECC-Q regeneration
- changed-sector accounting
- exact post-write re-extraction
- no estimated or inferred payload bytes

A full candidate is emitted only when the exact SK0501 replacement bytes and all other requested production payloads are found by the recursive loose-file, ZIP or retained-checkpoint scanner.
