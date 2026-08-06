# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Actual executable sparse package verified: 21/21 assets
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 37 assets

## Current batch

### Batch 165 — PASS REAL FILE LIBRARY PAYLOAD EXECUTION

The recovery track has moved beyond hash-only manifests. A real pristine Disc 1 archive and a retained executable sparse raw-sector package were materialized from File Library, applied locally, independently audited, and re-extracted into exact whole assets.

## Exact real inputs

### Pristine Disc 1

- archive: `015 Sakura Taisen 2 Disc 1 of 3 (J) (2)(1).zip`
- archive size: `458,507,639`
- archive SHA-256: `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- extracted BIN size: `659,293,824`
- extracted BIN SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`

### Executable sparse package

- package: `ST2R41_CD1_MASTER_BUILD_V29.zip`
- package size: `29,017,199`
- package SHA-256: `367bfb9e0f921124135c8c80c559c82c60a79de43573ca04a768abf6a251e47c`
- apply contract: `ST2_CD1_MASTER_BUILD_V29/APPLY_STATIC21_PATCH.py`
- sparse delta directory: `ST2_CD1_MASTER_BUILD_V29/STATIC21_RAW_SECTOR_SPARSE_DELTAS`

Package Python was not executed by the new recovery path. Literal metadata was parsed with AST and the sparse JSON deltas were independently applied.

## Actual execution gates

- source Disc size and SHA-256: PASS
- changed raw sectors: `609`
- original-sector SHA Expected Write: PASS 609/609
- per-span Expected Write SHA: PASS
- patched-sector SHA-256: PASS 609/609
- original MODE1/2352 EDC/ECC: PASS 609/609
- patched MODE1/2352 EDC/ECC: PASS 609/609
- unregistered changed sectors: `0`
- complete candidate Disc SHA-256: `8ceff2afb22e080469ad1adcc8f84f85d45c6b5e838df101beba70f00e3b0861`
- whole-asset re-extraction: PASS 21/21

## Recovered exact battle/static assets

- final banks: `SYSTEM`, `SYS14`
- B117 common banks: `SYS06`, `SYS28`, `SYS30`, `SYS32`, `SYS35`, `SYS38`, `SYS39`, `SYS40`, `SYS41`, `SYS42`, `SYS43`, `SYS44`, `SYS48`, `SYS50`
- B116 banks: `SYS20`, `SYS47`, `STNSYS02`, `SYS21`, `STNSYS03`

These 21 assets are part of the previously established 39/58 local byte scope. Batch165 does not inflate the physical count; it proves that retained real payloads can be safely executed and converted into reusable exact assets.

## New Batch165 components

- `tools/recover_assets_from_sparse_packages.py`
- `tools/verify_sparse_package_mode1.py`
- `manifests/BATCH165_REAL_LIBRARY_SPARSE_RECOVERY.json`
- `START_B165_RECOVER_REAL_SPARSE_PACKAGE.cmd`
- `.github/workflows/batch165-sparse-recovery.yml`
- `reports/BATCH165_REPORT.md`

## Story/movie production scope retained

- earlier story MES and SKCM assets: 30
- promoted compiled story BIN assets: 4
  - `SAKURA1/SK0403.BIN`
  - `SAKURA1/SK0504.BIN`
  - `SAKURA1/SK0501.BIN`
  - `SAKURA1/SK0502.BIN`
- Korean-subtitled movie assets: 3
- total exact production assets: 37
- subtitle events: 33

## Mandatory safety policy

- no package Python execution;
- no estimated or inferred game bytes;
- exact source Disc SHA required;
- exact original-sector and span-level Expected Write required;
- exact patched-sector SHA required;
- MODE1 EDC, ECC-P and ECC-Q required;
- complete candidate Disc SHA required;
- whole-asset re-extraction SHA required;
- no game, font, asset, movie or full Disc bytes committed to GitHub.

## Next production work

Run the Batch165 recovery path over the remaining retained executable sparse packages and master builds, merge unique exact assets by complete SHA-256, and promote only assets outside the already proven 39/58 physical scope. Story/movie production remains active in parallel through the 37-asset Batch164 manifest.
