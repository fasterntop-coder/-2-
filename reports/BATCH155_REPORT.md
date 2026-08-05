# Batch 155 — B113 nineteen-asset exact recovery promotion

## Result

PASS_TOOLCHAIN_COMMITTED

The verified Batch113 cumulative battle/static baseline is now recoverable without the later B118 workbook. A fixed manifest records all nineteen exact Korean assets using their historical LBA, size and re-extracted SHA-256.

## Exact scope

- PBOOK graphics: 3
- battle/system MES banks: 16
- total exact assets: 19
- historical changed raw sectors: 492
- historical LBA conflicts: 0
- historical MODE1/2352 EDC/ECC: 492/492 PASS
- historical re-extraction: 19/19 PASS

## Added

- `manifests/BATCH113_19_EXACT_TARGETS.json`
- `START_B155_RECOVER_BATCH113_19_ASSETS.cmd`

The launcher scans loose files, ZIP members and 659,293,824-byte MODE1/2352 checkpoints through the existing exact recovery engine. It emits an asset only when complete size and SHA-256 match the manifest.

## Safety

- no copyrighted game or translated asset bytes committed
- no estimated payloads
- no hash inversion
- raw checkpoints decoded from sector user data only
- whole-asset SHA-256 required before output
- historical Expected Write, changed-sector, EDC/ECC and re-extraction certificates remain authoritative for integration

## Production consequence

This promotes the battle/static baseline from a workbook-dependent recovery route to a direct fixed recovery route. Recovered assets can be placed beside Batch154 story/movie assets and fed into the cumulative production integration path.
