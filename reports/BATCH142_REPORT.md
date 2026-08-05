# ST2R41 Batch 142 — B110 Exact Asset Recovery Pivot

## Status

`PASS_EXACT_RECOVERY_TOOLCHAIN_READY_REAL_BYTES_PENDING`

## Lineage correction

The PBOOK_BT target SHA-256
`4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`
is the verified Batch110 independent reconstruction, not the missing historical
Batch82/83 byte-identical asset.

Batch110 already passed:

- active text 36/36
- non-text preservation 23/23
- inactive/unreferenced/alias preservation 4/4
- descriptor codec roundtrip 63/63
- changes outside active ranges 0
- MODE1/2352 EDC/ECC
- five-asset re-extraction 5/5

## Work completed

- Added `tools/recover_pbook_bt_b110.py`.
- Added exact B110 lineage manifest.
- Added Windows recursive scan launcher.
- Scanner supports loose 87,712-byte assets, raw Disc 1 BIN images and ZIP members.
- It emits only the pristine source SHA or verified B110 candidate SHA.
- No whole disc image is copied or distributed.
- Added raw-sector and ZIP-seek synthetic self-tests to GitHub Actions.

## Active paths

1. Recover the exact B110 candidate directly from any retained B110/later full BIN or ZIP.
2. Recover the pristine source directly from an original Disc 1 BIN or ZIP.
3. Keep palette-transfer inference as a fallback only when exact B110 bytes are unavailable.

## Exact gates

- Pristine PBOOK_BT: `43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64`
- Verified B110 candidate: `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`
- Pristine Disc 1: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- B110 five-asset Disc 1: `c6fc9827ee5d8ae17c918a8d7468faa4769601e13329c7485b3df53d5fd17c14`

## Safety result

No unverified asset or patch was emitted.
