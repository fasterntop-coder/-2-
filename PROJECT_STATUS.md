# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local scope: 39/58
- Historical battle/static certificate: 58/58
- Direct fixed recovery baseline: 19 exact B113 assets
- Exact story/movie production scope: 33 assets

## Current batch

### Batch 155 — PASS EXACT BASELINE PROMOTION

The verified Batch113 nineteen-asset cumulative battle/static baseline is now recoverable directly from retained loose files, ZIP archives or raw MODE1/2352 checkpoint BINs. The recovery route no longer depends on locating or parsing the later B118 workbook.

## Direct exact battle/static scope

- PBOOK graphics: 3
- battle/system MES banks: 16
- exact assets: 19
- historical changed raw sectors: 492
- historical LBA conflicts: 0
- historical MODE1/2352 EDC/ECC: 492/492 PASS
- historical re-extraction: 19/19 PASS

## New components

- `manifests/BATCH113_19_EXACT_TARGETS.json`
- `START_B155_RECOVER_BATCH113_19_ASSETS.cmd`
- `reports/BATCH155_REPORT.md`

Every output still requires complete size and whole-asset SHA-256 equality. Raw checkpoints are decoded sector-by-sector from the 2,048-byte user-data area.

## Story/movie production scope

The Batch154 production manifest remains active:

- Batch 51 story MES: 9 assets
- Batch 52 story MES: 18 assets
- Batch 62 SKCM story/system dialogue: 3 assets
- Batch 64 Korean-subtitled movies: 3 CAK assets / 33 subtitle events
- exact story/movie production assets: 33

## Cumulative production path

Recovered B113 assets and B51/B52/B62/B64 translated assets are collected into the same local vault. The production builder then applies exact recovered replacements to the pristine Disc 1 only after:

1. full source BIN size and SHA-256 gate;
2. per-asset Expected Write source SHA-256 gate;
3. exact replacement SHA-256 gate;
4. MODE1/2352 EDC, ECC-P and ECC-Q regeneration;
5. changed-sector accounting;
6. exact re-extraction of every applied asset.

## Safety

- pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- no game, translated asset, font or movie bytes committed
- no estimated or inferred payloads
- failed Expected Write, EDC/ECC, sector accounting or re-extraction deletes the candidate

## Active execution dependency

A real cumulative BIN now requires retained checkpoint BIN/ZIP or loose translated files containing any of the fixed B113 nineteen assets and B51/B52/B62/B64 story/movie assets, together with the exact pristine Disc 1 BIN. Any exact recovered subset can be promoted into a verified partial candidate.
