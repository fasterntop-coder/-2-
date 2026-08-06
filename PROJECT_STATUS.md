# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Actual executable sparse package verified: 21/21 assets
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 39 assets

## Current batch

### Batch 167 — PASS SK1304 EXACT PRODUCTION PROMOTION

`SAKURA1/SK1304.BIN` has been promoted from the completed Batch61 dialogue QA set into the executable exact production scope.

## Newly promoted story asset

### SK1304

- LBA: `46008`
- size: `44,464`
- source SHA-256: `591e9b23b035b3bb5786043318695c865d771d22aa8f53fbcc433359b04418f2`
- replacement SHA-256: `ff6e9b29a6ba76f8ee706f55041a9f83bb6246f24061efbfd00d41d042a54722`
- records reviewed: `149/149`
- translated records: `146`
- control records preserved: `3` (`47`, `113`, `126`)
- FFFD records: `112`, `125`
- confirmed translation reuse: `47`
- new translations: `99`
- font slots: `236 used + 15 preserved / 252`
- remaining font slots: `1`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- validation: `PASS_OFFLINE`

## Exact production scope

- earlier story MES and SKCM assets: `30`
- promoted compiled story BIN assets: `6`
  - `SAKURA1/SK0403.BIN`
  - `SAKURA1/SK0504.BIN`
  - `SAKURA1/SK0501.BIN`
  - `SAKURA1/SK0502.BIN`
  - `SAKURA1/SK0505.BIN`
  - `SAKURA1/SK1304.BIN`
- Korean-subtitled movie assets: `3`
- total exact production assets: `39`
- subtitle events: `33`

## Batch167 components

- `manifests/SK1304_FINAL_EXACT_TARGET.json`
- `START_B167_PRODUCTION_WITH_SK1304.cmd`
- `.github/workflows/batch167-production.yml`
- `reports/BATCH167_REPORT.md`

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

Promote the completed Batch62 `SKCM02.BIN`, `SKCM04.BIN`, and `SKCM05.BIN` exact assets, then continue executable sparse-package recovery outside the proven 39/58 battle/static physical scope.
