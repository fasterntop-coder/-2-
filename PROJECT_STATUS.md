# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Exact battle-bank package scope: 55/55
- Exact PBOOK recovery contract: 3/3
- Deterministic battle/static target: 58/58
- Historical battle/static certificate: 58/58
- Exact story/movie production scope: 42 assets

## Current batch

### Batch 173 — PASS CHECKPOINT BIN PBOOK RECOVERY PATH

The PBOOK recovery path can now recover the exact 29 registered raw sectors directly from retained full Disc checkpoint BINs or BIN entries inside ZIP archives. Loose raw-sector sidecars are no longer the only recovery source.

## Batch173 components

- `tools/recover_pbook_sectors_from_checkpoint_bins.py`
- `START_B173_RECOVER_PBOOK_FROM_CHECKPOINT_BINS.cmd`
- `.github/workflows/batch173-pbook-checkpoint-recovery.yml`
- `reports/BATCH173_REPORT.md`

## Batch173 acceptance contract

- Parse the literal Batch110 sector map through AST without importing or executing legacy code.
- Require exactly 29 PBOOK sectors: BT 12, EC 5, RC 12.
- Scan only 659,293,824-byte loose BINs and equal-sized BIN entries inside ZIP archives.
- Accept each target LBA only when its complete 2,352-byte raw-sector SHA-256 equals the registered patched-sector oracle.
- Independently verify MODE1 sync, mode, EDC, reserved bytes, ECC-P and ECC-Q.
- Require pristine Disc 1 SHA-256 `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106` before reconstruction.
- Require source whole-asset Expected Write SHA-256 and replacement whole-asset SHA-256.
- Optional Disc build requires exact changed-sector accounting and 3/3 re-extraction.

## PBOOK exact targets

### PBOOK_BT.CG

- LBA: `15609`
- size: `87,712`
- source SHA-256: `43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64`
- replacement SHA-256: `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`
- changed sectors: `12`

### PBOOK_EC.CG

- LBA: `15652`
- size: `87,456`
- source SHA-256: `3118ecdf03d7225f9666298b7c93b357c276bbdc27ce0b7020baca12003db3bc`
- replacement SHA-256: `378d92a4daf3db00d7c172ae8d233fad1fe3e1452cb979e9bd8b5610220152f5`
- changed sectors: `5`

### PBOOK_RC.CG

- LBA: `15695`
- size: `58,208`
- source SHA-256: `56f8607a5c3ab6c5ad79b1b3de2910822f3880fa7f2e3938b273a1dfa27bc201`
- replacement SHA-256: `c5bc0866ea5581f64bccb0a9da1c6baf53c77601fa247469441e49d0eaae4907`
- changed sectors: `12`

## Static closure state

The deterministic static definition remains 58/58:

- Batch137 exact battle banks: 55/55
- PBOOK exact targets: 3/3

A physical combined 58-asset candidate requires:

- pristine Disc 1 BIN, size `659,293,824`, exact SHA-256 above;
- `ST2R41_BATCH137_FIFTYFIVE_ASSET_EXACT_RECOVERY_PATCH.zip`, SHA-256 `48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c`;
- either all 29 exact Batch110 PBOOK patched raw-sector sidecars, the three complete PBOOK replacement payloads, or retained checkpoint BINs containing the registered 29 patched sectors.

## Mandatory safety policy

- no estimated or inferred payload bytes;
- exact pristine Disc SHA-256 required;
- exact source SHA-256 Expected Write required;
- exact replacement size and SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q integrity required;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no copyrighted game, font, asset, movie or full Disc bytes committed to GitHub.
