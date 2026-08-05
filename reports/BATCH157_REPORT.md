# Batch 157 — B115 thirty-three-asset exact recovery baseline

## Status

`PASS_B115_33_ASSET_DIRECT_RECOVERY_PATH`

## Actual change

The direct exact battle/static recovery baseline advances from Batch114's cumulative 25 assets to Batch115's cumulative 33 assets.

New exact B115 banks:

- SYS13
- SYS12
- SYS18
- SYS45
- SYS10
- SYS19
- SYS46
- STNSYS01

All eight entries use the retained historical LBA, complete file size and whole-asset SHA-256 from the verified Batch115 re-extraction lineage.

## Historical gates

- cumulative assets: 33
- changed raw sectors: 899
- LBA conflicts: 0
- changes outside declared sectors: 0
- MODE1/2352 EDC/ECC: 899/899 PASS
- re-extraction: 33/33 PASS
- verification BIN SHA-256: `cb22622232aa13a8cc767f37563798ce8b6cdbe4e44b7e16439fab281ae2a1d1`
- CUE SHA-256: `4e2f08c58c938afa51f6b11408ed6cd1742d2d5b777675b97fb0ba18d956c7fc`

## Components

- `manifests/BATCH115_33_EXACT_TARGETS.json`
- `START_B157_RECOVER_BATCH115_33_ASSETS.cmd`
- existing `tools/recover_exact_assets_from_checkpoints.py`

The scanner accepts only complete loose assets, ZIP members or MODE1/2352 checkpoint-extracted assets whose size and SHA-256 exactly match the manifest. No asset bytes are reconstructed from hashes.

## Production effect

Any recovered subset can be placed in the same local vault used by the Batch154 story/movie production builder. This makes 33 verified battle/static assets directly discoverable without parsing historical workbooks.

## Next production step

Promote the B116 nine-bank lineage, then the B117 fourteen-bank lineage, while keeping SYSTEM and SYS14 on the exact B124/B183 path.
