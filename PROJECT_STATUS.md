# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Exact battle-bank package scope: 55/55
- Exact PBOOK recovery contract: 3/3
- Deterministic battle/static target: 58/58
- Historical battle/static certificate: 58/58
- Exact story/movie production scope: 42 assets

## Current batch

### Batch 170 — PASS PBOOK THREE-ASSET EXACT RECOVERY CONTRACT

The three PBOOK assets outside the Batch137 55-bank package are now registered as one strict executable recovery manifest.

## PBOOK exact targets

### PBOOK_BT.CG

- LBA: `15609`
- size: `87,712`
- source SHA-256: `43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64`
- replacement SHA-256: `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`
- changed sectors: `12`
- lineage: independent Batch110 reconstruction, not historical Batch82 byte identity

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

## Batch170 components

- `manifests/PBOOK_3_EXACT_TARGETS.json`
- `START_B170_RECOVER_PBOOK_3_EXACT.cmd`
- `.github/workflows/batch170-pbook-static.yml`
- `reports/BATCH170_REPORT.md`

## Verification lineage

Batch110 previously verified the PBOOK trio in a five-asset Disc candidate:

- 87 unique changed sectors across PBOOK_BT, PBOOK_EC, PBOOK_RC, SYS26 and STNSYS00;
- zero LBA conflicts;
- zero unrelated changed sectors;
- MODE1/2352 EDC/ECC PASS;
- re-extraction 5/5 PASS.

The PBOOK-only portion is 29 changed sectors. The new launcher accepts only complete exact replacement payloads and then repeats pristine Disc SHA, per-asset Expected Write, EDC/ECC rebuild, changed-sector accounting and whole-asset re-extraction gates.

## Static closure state

The deterministic static definition is now 58/58:

- Batch137 exact battle banks: 55/55
- PBOOK exact targets: 3/3

A physical combined 58-asset candidate still requires these exact runtime inputs to coexist in one scan root:

- pristine Disc 1 BIN, size `659,293,824`, SHA-256 `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`;
- `ST2R41_BATCH137_FIFTYFIVE_ASSET_EXACT_RECOVERY_PATCH.zip`, SHA-256 `48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c`;
- the three PBOOK replacement payloads matching the registered SHA-256 values.

## Mandatory safety policy

- no estimated or inferred payload bytes;
- exact pristine Disc SHA-256 required;
- exact source SHA-256 Expected Write required;
- exact replacement size and SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q regeneration required;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no copyrighted game, font, asset, movie or full Disc bytes committed to GitHub.
