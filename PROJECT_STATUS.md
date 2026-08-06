# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Actual executable sparse package verified: 21/21 assets
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 38 assets

## Current batch

### Batch 166 — PASS SK0505 EXACT PRODUCTION PROMOTION

`SAKURA1/SK0505.BIN` has been promoted from the completed Batch61 dialogue QA set into the executable exact production scope.

## Newly promoted story asset

### SK0505

- LBA: `45989`
- size: `37,136`
- source SHA-256: `c2f59f4711a55c722e166ab4114f0f1ac88db459e3312b94a2a916fc01aa23ce`
- replacement SHA-256: `102709b60da35894b03d2f03716b8a14735f6711031b28fad7cc995cffe73104`
- records reviewed: `86/86`
- translated records: `85`
- control records preserved: `1`
- font slots: `209 used + 15 preserved / 237`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- validation: `PASS_OFFLINE`

## Exact production scope

- earlier story MES and SKCM assets: `30`
- promoted compiled story BIN assets: `5`
  - `SAKURA1/SK0403.BIN`
  - `SAKURA1/SK0504.BIN`
  - `SAKURA1/SK0501.BIN`
  - `SAKURA1/SK0502.BIN`
  - `SAKURA1/SK0505.BIN`
- Korean-subtitled movie assets: `3`
- total exact production assets: `38`
- subtitle events: `33`

## Batch166 components

- `manifests/SK0505_FINAL_EXACT_TARGET.json`
- `START_B166_PRODUCTION_WITH_SK0403_SK0504_SK0501_SK0502_SK0505.cmd`
- `.github/workflows/batch166-production.yml`
- `reports/BATCH166_REPORT.md`

## Battle/static recovery baseline retained

Batch165 independently executed the retained `ST2R41_CD1_MASTER_BUILD_V29.zip` sparse package against the exact pristine Disc 1 and passed:

- original-sector Expected Write: `609/609`
- patched-sector SHA-256: `609/609`
- original and patched MODE1/2352 EDC/ECC: `609/609`
- unregistered changed sectors: `0`
- candidate Disc SHA-256: `8ceff2afb22e080469ad1adcc8f84f85d45c6b5e838df101beba70f00e3b0861`
- whole-asset re-extraction: `21/21`

The 21 recovered assets remain within the established 39/58 physical byte scope and do not inflate that count.

## Mandatory safety policy

- no package Python execution for untrusted retained packages;
- no estimated or inferred game bytes;
- exact pristine Disc SHA-256 required;
- exact per-asset source SHA-256 Expected Write required;
- exact replacement size and SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q required;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no game, font, asset, movie or full Disc bytes committed to GitHub.

## Next work

Continue executable sparse-package recovery for battle/static assets outside the proven 39/58 physical scope, while promoting the next fully compiled story BIN with exact source/replacement SHA evidence.
