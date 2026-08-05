# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local scope: 39/58
- Historical battle/static certificate: 58/58
- Exact story/movie production scope: 33 assets

## Current batch

### Batch 154 — PASS PRODUCTION TOOLCHAIN

The active direction has changed from repeated recovery-only analysis to executable Korean story and movie production integration.

## Exact production scope

The following retained historical translation outputs are now fixed in one trusted manifest:

- Batch 51 story MES: 9 assets
- Batch 52 story MES: 18 assets
- Batch 62 SKCM story/system dialogue: 3 assets
- Batch 64 Korean-subtitled movies: 3 CAK assets / 33 subtitle events

Total:

- story assets: 30
- movie assets: 3
- exact production assets: 33

## New production components

- `manifests/CD1_PRODUCTION_STORY_MOVIE_TARGETS.json`
- `tools/recover_integrate_production_assets.py`
- `START_B154_PRODUCTION_INTEGRATION.cmd`
- `reports/BATCH154_REPORT.md`

## Production path

The Batch154 builder recursively scans loose files, ZIP archives and full raw checkpoint BINs. It accepts a translated asset only when the complete size and replacement SHA-256 match the trusted manifest.

When the exact pristine Disc 1 BIN is present, it performs:

1. full source BIN size and SHA-256 gate;
2. per-asset source SHA-256 Expected Write gate;
3. exact replacement insertion;
4. MODE1/2352 EDC, ECC-P and ECC-Q regeneration;
5. complete changed-sector accounting;
6. exact re-extraction of every applied asset;
7. local BIN/CUE, result JSON and sparse raw-sector patch generation.

Partial production candidates are allowed only for exact recovered replacement assets. No guessed bytes are accepted.

## Safety

- pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- no game, translated asset, font or movie bytes committed
- failed Expected Write, EDC/ECC, sector accounting or re-extraction deletes the candidate
- all binary build outputs remain local

## Active execution dependency

A real production candidate now requires the exact B51/B52/B62/B64 replacement files, or a retained checkpoint BIN/ZIP containing them, together with the exact pristine Disc 1 BIN. As soon as any subset is recovered, the builder can create a verified partial cumulative candidate instead of returning to analysis-only work.

## Next production work

1. recover and integrate the 33 exact story/movie assets from retained archives;
2. record actual applied asset and subtitle-event counts;
3. continue untranslated story or movie content as new production assets;
4. merge the verified story/movie candidate with the exact battle/static baseline before SSF and hardware validation.
