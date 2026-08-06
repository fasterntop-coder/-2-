# ST2R41 Batch 166 — SK0505 exact production promotion

## Status

`PASS_SK0505_EXACT_PRODUCTION_TARGET_REGISTERED`

## Promoted asset

- ISO path: `SAKURA1/SK0505.BIN`
- LBA: `45989`
- size: `37,136`
- source SHA-256: `c2f59f4711a55c722e166ab4114f0f1ac88db459e3312b94a2a916fc01aa23ce`
- replacement SHA-256: `102709b60da35894b03d2f03716b8a14735f6711031b28fad7cc995cffe73104`
- records reviewed: `86/86`
- translated records: `85`
- control records preserved: `1`
- font slots: `209 used + 15 preserved / 237`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- validation: `PASS_OFFLINE`

## Production scope

The exact story/movie production composition increases from 37 to 38 assets:

- story assets: `35`
- movie assets: `3`
- subtitle events: `33`

## Added components

- `manifests/SK0505_FINAL_EXACT_TARGET.json`
- `START_B166_PRODUCTION_WITH_SK0403_SK0504_SK0501_SK0502_SK0505.cmd`
- `.github/workflows/batch166-production.yml`

## Mandatory gates retained

- pristine Disc 1 size and SHA-256
- per-asset source SHA-256 Expected Write
- exact replacement size and SHA-256
- MODE1/2352 EDC, ECC-P and ECC-Q regeneration
- changed-sector accounting
- exact whole-asset re-extraction
- no estimated or inferred payload bytes

No copyrighted replacement binary or full Disc image is committed.
