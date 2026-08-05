# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local scope: 39/58
- Historical battle/static certificate: 58/58
- Direct fixed recovery baseline: 33 exact B115 assets
- Exact story/movie production scope: 33 assets

## Current batch

### Batch 157 — PASS DIRECT EXACT BASELINE 33

The direct exact battle/static recovery baseline has advanced through two cumulative production steps in this run:

- Batch156: B114 cumulative 25 assets
- Batch157: B115 cumulative 33 assets

The route no longer depends on parsing B114/B115 workbooks at execution time. Retained loose files, ZIP members and MODE1/2352 checkpoint BINs are scanned directly and accepted only by complete size plus whole-asset SHA-256 equality.

## B115 direct exact scope

- PBOOK graphics: 3
- battle/system MES banks: 30
- exact assets: 33
- historical changed raw sectors: 899
- historical LBA conflicts: 0
- historical changes outside declared sectors: 0
- historical MODE1/2352 EDC/ECC: 899/899 PASS
- historical re-extraction: 33/33 PASS
- historical verification BIN SHA-256: `cb22622232aa13a8cc767f37563798ce8b6cdbe4e44b7e16439fab281ae2a1d1`

## Newly promoted banks

Batch114:

- SYS11, SYS37, SYS09, SYS36, SYS15, SYS16

Batch115:

- SYS13, SYS12, SYS18, SYS45, SYS10, SYS19, SYS46, STNSYS01

## New components

- `manifests/BATCH114_25_EXACT_TARGETS.json`
- `START_B156_RECOVER_BATCH114_25_ASSETS.cmd`
- `reports/BATCH156_REPORT.md`
- `manifests/BATCH115_33_EXACT_TARGETS.json`
- `START_B157_RECOVER_BATCH115_33_ASSETS.cmd`
- `reports/BATCH157_REPORT.md`

## Story/movie production scope

The Batch154 production manifest remains active:

- Batch51 story MES: 9 assets
- Batch52 story MES: 18 assets
- Batch62 SKCM story/system dialogue: 3 assets
- Batch64 Korean-subtitled movies: 3 CAK assets / 33 subtitle events
- exact story/movie production assets: 33

Recovered battle/static assets and story/movie assets are collected into the same local production vault. The production builder applies exact recovered replacements to pristine Disc 1 only after source BIN SHA, per-asset Expected Write, replacement SHA, MODE1 EDC/ECC, changed-sector accounting and re-extraction gates pass.

## Safety

- pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- no game, translated asset, font or movie bytes committed
- no estimated or inferred payloads
- failed gates delete the candidate

## Next production work

Promote the B116 nine-bank exact lineage, then B117's fourteen-bank lineage. SYSTEM and SYS14 remain on the exact B124/B183 path before final 58/58 cumulative integration.
