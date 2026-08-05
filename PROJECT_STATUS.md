# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 35 assets

## Current batch

### Batch 162 — PASS SK0504 EXACT PRODUCTION PROMOTION

A second fully compiled story BIN has been promoted into the executable production scope.

## Exact promoted story assets

### SK0403

- ISO path: `SAKURA1/SK0403.BIN`
- LBA: 45626
- size: 113392
- source SHA-256: `2736d124c75afcf99cf0d8646427ba9478b84215c8de64fb29aa73f7cefa9b1e`
- replacement SHA-256: `94576a14ff92abff690fde9acdd9e5673b834f7d62391be39971f7d70e4932b5`
- reverse decode: 506/506 PASS

### SK0504

- ISO path: `SAKURA1/SK0504.BIN`
- LBA: 45926
- size: 127140
- source SHA-256: `52d5429c1d0e4029406d63f9b780bda3d78bb3de90233d4e5de488d2713d07bb`
- replacement SHA-256: `619bee36d6e821665df9e09a0b0ffa36021b58fdbda0c3fbf0f81a9e7421f4ac`
- records reviewed: 726/726
- translated records: 725
- control records preserved: 1
- capacity overflow: 0
- line overflow: 0
- Japanese remaining: 0
- reverse-decode mismatches: 0
- validation: PASS_OFFLINE

## Production scope

The active exact production composition is now:

- earlier story MES and SKCM assets: 30
- promoted compiled story BIN assets: 2
- Korean-subtitled movie assets: 3
- total exact production assets: 35
- subtitle events: 33

## New components

- `manifests/SK0504_FINAL_EXACT_TARGET.json`
- `START_B162_PRODUCTION_WITH_SK0403_SK0504.cmd`
- `.github/workflows/batch162-production.yml`
- `reports/BATCH162_REPORT.md`

## Execution

The Batch162 launcher composes the 35-asset manifest, recursively scans loose files, ZIP archives and retained checkpoint BINs, and applies every exact recovered subset to a pristine Disc 1 candidate only after all mandatory gates pass.

## Mandatory safety gates

- pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- per-asset source SHA-256 Expected Write
- complete replacement size and SHA-256
- MODE1/2352 EDC, ECC-P and ECC-Q regeneration
- changed-sector accounting
- exact re-extraction of every applied asset
- no estimated or inferred payload bytes

## Battle/static recovery status

The repository knows and validates all 58 historical battle/static target hashes. Current physically reconstructed local byte scope remains 39/58 until the remaining exact payloads are recovered from loose files or checkpoint BIN/ZIP archives.

## Active byte dependency

A real Batch162 Disc candidate requires the exact pristine Disc 1 BIN and at least one exact replacement asset from the 35-asset production manifest. Full 35/35 production integration requires the exact B51/B52/B62/B64 assets plus `SK0403_KR_R41_FINAL.BIN` and `SK0504.BIN` matching their registered replacement SHA-256 values.
