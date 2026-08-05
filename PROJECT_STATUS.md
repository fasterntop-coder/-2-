# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 33 assets

## Current batch

### Batch 160 — PASS FULL 58-ASSET RECOVERY CONTRACT

The direct exact battle/static recovery path has advanced through three cumulative stages in one production run:

- Batch158: B116 cumulative 42 assets
- Batch159: B117 cumulative 56 assets
- Batch160: B118 cumulative 58 assets

The execution path no longer depends on manually transcribing the historical B116/B117/B118 workbooks. A trusted B115 33-asset base and three small exact deltas are composed with strict lineage checks.

## Exact cumulative lineage

### B116

New banks:

- SYS20, SYS47, STNSYS02, SYS21, STNSYS03
- SYS23, SYS24, SYS22, SYS25

Historical gates:

- 42 assets
- 1,162 changed raw sectors
- EDC/ECC PASS
- re-extraction 42/42 PASS
- verification BIN SHA-256: `d318c3a5a0291483da6ee1626341f561ac26c34009be502dbe07222abd5b8088`

### B117

New banks:

- SYS06, SYS28, SYS30, SYS32, SYS35, SYS38, SYS39
- SYS40, SYS41, SYS42, SYS43, SYS44, SYS48, SYS50

Historical gates:

- 56 assets
- 1,568 changed raw sectors
- EDC/ECC PASS
- re-extraction 56/56 PASS
- verification BIN SHA-256: `83481538455dc236100629f60b2e9349d10ccef8e28141591464db2ff21bfd07`

### B118

Final banks:

- SYSTEM
- SYS14

Historical gates:

- 58 assets
- battle banks 55/55
- battle records 12,595/12,595
- 1,626 changed raw sectors
- LBA conflicts 0
- changes outside declared sectors 0
- EDC/ECC PASS
- re-extraction 58/58 PASS
- verification BIN SHA-256: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

## New components

- `tools/compose_exact_asset_lineage.py`
- `manifests/BATCH116_9_EXACT_DELTA.json`
- `manifests/BATCH117_14_EXACT_DELTA.json`
- `manifests/BATCH118_2_EXACT_DELTA.json`
- `START_B160_RECOVER_BATCH118_58_ASSETS.cmd`
- `reports/BATCH158_160_REPORT.md`

## Execution

The Batch160 launcher:

1. generates a validated B116 42-asset manifest;
2. generates a validated B117 56-asset manifest;
3. generates a validated B118 58-asset manifest;
4. scans loose assets, ZIP members and MODE1/2352 checkpoint BINs;
5. emits only complete assets whose size and target SHA-256 match exactly.

Lineage composition is aborted on base-batch discontinuity, cumulative-count mismatch, duplicate asset name, duplicate starting LBA, invalid size or invalid SHA-256.

## Story/movie production scope

The Batch154 production manifest remains active:

- Batch51 story MES: 9 assets
- Batch52 story MES: 18 assets
- Batch62 SKCM story/system dialogue: 3 assets
- Batch64 Korean-subtitled movies: 3 CAK assets / 33 subtitle events
- exact story/movie production assets: 33

Recovered battle/static and story/movie assets are collected in the local production vault. Final Disc application still requires pristine source SHA, per-asset Expected Write, exact replacement SHA, MODE1 EDC/ECC regeneration, changed-sector accounting and re-extraction.

## Safety

- pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- no game, translated asset, font or movie bytes committed
- no estimated or inferred payloads
- failed gates produce no accepted recovery asset or candidate

## Active byte dependency

The repository now knows and validates all 58 exact historical targets. A real 58/58 local vault still requires retained loose translated files or checkpoint BIN/ZIP byte streams containing those targets. Current physically reconstructed local byte scope remains 39/58 until those payloads are recovered.

## Next production work

Run the full 58-asset scanner over retained archives, promote every recovered exact asset into the integration vault, and merge that vault with the 33 exact story/movie production targets before SSF and hardware validation.
