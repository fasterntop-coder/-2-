# Batch 156 — B114 twenty-five-asset exact recovery baseline

## Status

`PASS_B114_25_ASSET_DIRECT_RECOVERY_PATH`

## Actual change

The direct exact battle/static recovery baseline advances from the Batch113 cumulative 19 assets to the Batch114 cumulative 25 assets.

New exact B114 banks:

- SYS11
- SYS37
- SYS09
- SYS36
- SYS15
- SYS16

All six entries use the retained historical LBA, complete file size and whole-asset SHA-256 from the verified Batch114/B115 re-extraction lineage.

## Historical gates

- cumulative assets: 25
- changed raw sectors: 666
- LBA conflicts: 0
- changes outside declared sectors: 0
- MODE1/2352 EDC/ECC: 666/666 PASS
- re-extraction: 25/25 PASS
- verification BIN SHA-256: `5b54f2f532e632d024f7aa44732cdaee4b52e1b7c587a1077bbe0d741f31c704`
- CUE SHA-256: `398a5ad35c06f0c7b010d74846023ee5b7e5d38ed2d3ab2f7f2c79a8e68be104`

## Components

- `manifests/BATCH114_25_EXACT_TARGETS.json`
- `START_B156_RECOVER_BATCH114_25_ASSETS.cmd`
- existing `tools/recover_exact_assets_from_checkpoints.py`

The scanner accepts only complete loose assets, ZIP members or MODE1/2352 checkpoint-extracted assets whose size and SHA-256 exactly match the manifest. No asset bytes are reconstructed from hashes.

## Next production step

Promote the B115 eight-bank cumulative 33-asset lineage and then join any recovered exact battle/static assets with the Batch154 story/movie production vault.
