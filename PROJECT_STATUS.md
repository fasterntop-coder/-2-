# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static package scope: 55/58
- Historical battle/static certificate: 58/58
- Exact story/movie production scope: 42 assets

## Current batch

### Batch 169 — PASS B137 55-ASSET EXACT PACKAGE LOCK

The retained `ST2R41_BATCH137_FIFTYFIVE_ASSET_EXACT_RECOVERY_PATCH.zip` was independently inspected without executing package code and is now locked as the exact executable recovery source for all 55 battle banks.

## B137 locked package

- size: `3,298,916`
- SHA-256: `48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c`
- exact assets: `55/55`
- changed raw sectors: `1,597`
- expected sectors excluding PBOOK: `1,597`
- MODE1/2352 EDC/ECC: `PASS`
- re-extraction: `55/55 PASS`
- verification Disc SHA-256: `b5e8fc8b1a5798d03a3f3bd21a87ce66b742c64a1d8ce3ed3d7dc8db9763d518`

## Batch169 components

- `tools/verify_batch137_exact_package.py`
- `.github/workflows/batch169-b137-package.yml`
- `reports/BATCH169_REPORT.md`

The verifier requires the whole ZIP SHA, every package-manifest member SHA, all 1,597 delta SHA values, 55 distinct assets, the EDC/ECC result, the 55/55 re-extraction result and the exact verification Disc SHA.

## Remaining static closure

The remaining three static assets are:

- `PBOOK_BT`
- `PBOOK_EC`
- `PBOOK_RC`

They require exact locked replacement payload lineage before executable 58/58 closure. No estimated or inferred bytes are accepted.

## Mandatory safety policy

- no package Python execution for untrusted retained packages;
- exact pristine Disc SHA-256 required for application;
- exact per-sector original SHA-256 Expected Write required;
- exact delta and patched-sector SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q required;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no game, font, asset, movie or full Disc bytes committed to GitHub.
