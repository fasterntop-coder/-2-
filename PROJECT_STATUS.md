# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 37 assets

## Current batch

### Batch 164 — PASS SK0502 EXACT PRODUCTION PROMOTION

A fourth fully compiled story BIN has been promoted into the executable production scope.

## Newly promoted asset

### SK0502

- ISO path: `SAKURA1/SK0502.BIN`
- LBA: 45825
- size: 107920
- source SHA-256: `8fb80c1353d9ceef632fc7198cf8e8ef045f41f08adcc43dbf7cbb9262273ea4`
- replacement SHA-256: `0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc`
- records reviewed: 518/518
- translated records: 517
- control records preserved: 1
- FFFD special controls preserved: 15/15
- font slots: 509 used + 15 preserved / 537
- font slots remaining: 13
- capacity overflow: 0
- line overflow: 0
- Japanese remaining: 0
- reverse-decode mismatches: 0
- validation: PASS_OFFLINE

## Previously promoted compiled story assets

- `SAKURA1/SK0403.BIN`
- `SAKURA1/SK0504.BIN`
- `SAKURA1/SK0501.BIN`

## Production scope

The active exact production composition is now:

- earlier story MES and SKCM assets: 30
- promoted compiled story BIN assets: 4
- Korean-subtitled movie assets: 3
- total exact production assets: 37
- subtitle events: 33

## New components

- `manifests/SK0502_FINAL_EXACT_TARGET.json`
- `START_B164_PRODUCTION_WITH_SK0403_SK0504_SK0501_SK0502.cmd`
- `.github/workflows/batch164-production.yml`
- `reports/BATCH164_REPORT.md`

## Execution

The Batch164 launcher composes the 37-asset manifest, recursively scans loose files, ZIP archives and retained checkpoint BINs, and applies every exact recovered subset to a pristine Disc 1 candidate only after all mandatory gates pass.

## Mandatory safety gates

- pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- per-asset source SHA-256 Expected Write
- complete replacement size and SHA-256
- MODE1/2352 EDC, ECC-P and ECC-Q regeneration
- changed-sector accounting
- exact re-extraction of every applied asset
- no estimated or inferred payload bytes

## Battle/static recovery status

The repository knows and validates all 58 historical battle/static target hashes. Current physically reconstructed local byte scope remains 39/58 until the remaining exact payloads are recovered from loose files or checkpoint BIN/ZIP archives.

## Active byte dependency

A real Batch164 Disc candidate requires the exact pristine Disc 1 BIN and at least one exact replacement asset from the 37-asset production manifest. Full 37/37 production integration requires the exact B51/B52/B62/B64 assets plus the four promoted compiled story BINs matching their registered replacement SHA-256 values.
