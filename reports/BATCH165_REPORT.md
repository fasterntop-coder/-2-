# Batch 165 — Real File Library sparse-package recovery

## Status

`PASS_REAL_LIBRARY_SPARSE_PATCH_APPLIED_AND_21_ASSETS_REEXTRACTED`

Batch165 moved the battle/static recovery path from hash-only metadata to an actual executable payload test. The exact pristine Disc 1 archive and a retained executable sparse raw-sector package were materialized from File Library, applied locally, and audited end to end.

## Exact inputs

### Pristine Disc 1 archive

- archive: `015 Sakura Taisen 2 Disc 1 of 3 (J) (2)(1).zip`
- archive size: `458,507,639`
- archive SHA-256: `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- extracted BIN size: `659,293,824`
- extracted BIN SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`

### Sparse package

- package: `ST2R41_CD1_MASTER_BUILD_V29.zip`
- package size: `29,017,199`
- package SHA-256: `367bfb9e0f921124135c8c80c559c82c60a79de43573ca04a768abf6a251e47c`
- literal apply contract: `ST2_CD1_MASTER_BUILD_V29/APPLY_STATIC21_PATCH.py`
- delta directory: `ST2_CD1_MASTER_BUILD_V29/STATIC21_RAW_SECTOR_SPARSE_DELTAS`

The package Python was not executed by the new recovery implementation. Only literal constants were parsed with `ast.literal_eval`, and the JSON sparse deltas were independently applied.

## Actual execution result

- source Disc SHA gate: PASS
- changed raw sectors: `609`
- original-sector SHA Expected Write: PASS 609/609
- per-span Expected Write SHA: PASS
- patched-sector SHA: PASS 609/609
- MODE1/2352 original EDC/ECC: PASS 609/609
- MODE1/2352 patched EDC/ECC: PASS 609/609
- unregistered changed sectors: `0`
- complete candidate Disc SHA-256: `8ceff2afb22e080469ad1adcc8f84f85d45c6b5e838df101beba70f00e3b0861`
- exact whole-asset re-extraction: PASS 21/21

## Recovered exact assets

The package yielded exact local bytes for:

- final banks: `SYSTEM`, `SYS14`
- B117 common banks: `SYS06`, `SYS28`, `SYS30`, `SYS32`, `SYS35`, `SYS38`, `SYS39`, `SYS40`, `SYS41`, `SYS42`, `SYS43`, `SYS44`, `SYS48`, `SYS50`
- later B116 banks: `SYS20`, `SYS47`, `STNSYS02`, `SYS21`, `STNSYS03`

All complete sizes and SHA-256 values match `manifests/BATCH165_REAL_LIBRARY_SPARSE_RECOVERY.json`.

## New executable components

- `tools/recover_assets_from_sparse_packages.py`
- `tools/verify_sparse_package_mode1.py`
- `manifests/BATCH165_REAL_LIBRARY_SPARSE_RECOVERY.json`
- `START_B165_RECOVER_REAL_SPARSE_PACKAGE.cmd`
- `.github/workflows/batch165-sparse-recovery.yml`

## Safety behavior

- package Python is never executed;
- source Disc size and SHA-256 are mandatory;
- every source sector requires its declared original SHA-256;
- every modified span requires its old-byte SHA-256 Expected Write match;
- every final sector requires its declared patched SHA-256;
- all changed MODE1 sectors require valid EDC, ECC-P and ECC-Q;
- the streamed complete candidate Disc SHA must match the package target;
- every recovered asset must match its complete target SHA-256;
- no game, font, asset or full Disc bytes are committed to GitHub.

## Scope note

The 21 recovered assets are part of the previously established 39/58 physical exact-byte scope, so Batch165 does not falsely increase that count. Its concrete advance is that actual retained payloads were found, applied, independently validated and converted into reusable whole-asset files rather than remaining report-only evidence.
