# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact battle/static local bytes: 39/58
- Historical battle/static certificate: 58/58
- Actual executable sparse package verified: 21/21 assets
- Direct deterministic recovery target: 58/58 exact assets
- Exact story/movie production scope: 42 assets

## Current batch

### Batch 168 — PASS BATCH62 SKCM EXACT PRODUCTION PROMOTION

The three completed Batch62 character/auxiliary story assets have been promoted into the executable exact production scope.

## Newly promoted story assets

### SKCM02

- ISO path: `SAKURA1/SKCM02.BIN`
- LBA: `46030`
- size: `129652`
- source SHA-256: `ca7631c90c264b91a13e96dd21d656c59048b9961b182e3d261c146811c883af`
- replacement SHA-256: `0a2d0edf358b8fe6ab6edbc058e7e1263fc466706312bec43fd9994eb38419d9`
- records: `414`
- translated: `413`
- control preserved: `1` (`336`)

### SKCM04

- ISO path: `SAKURA1/SKCM04.BIN`
- LBA: `46094`
- size: `91196`
- source SHA-256: `59b7fdb48784a510c5227dd1f3f3ef8c1172c7b00e692ade0d7ffb7ae44e0e29`
- replacement SHA-256: `c3e78d0b32b87d58d720c0fdd616fbc2fba232b306abe8c528d66a524664c4f8`
- records: `139`
- translated: `138`
- control preserved: `1` (`138`)

### SKCM05

- ISO path: `SAKURA1/SKCM05.BIN`
- LBA: `46139`
- size: `91416`
- source SHA-256: `99375992aedd61f37cec7fdf7574581abcd7e222be8b01aae0937257752dc257`
- replacement SHA-256: `cfd966f1cc1783f0da0f988aba92bd7591237cacb10c633da0063ce1f71c29f4`
- records: `125`
- translated: `124`
- control preserved: `1` (`120`)

## Batch62 closure

- files processed: `3/3`
- records reviewed: `678/678`
- translated records: `675`
- control records preserved: `3`
- complex-control translated records: `45`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- source inventory completion: `100%`
- hardware confirmation: pending

## Exact production scope

- earlier story MES assets: `30`
- promoted compiled story BIN assets: `9`
- Korean-subtitled movie assets: `3`
- total exact production assets: `42`
- subtitle events: `33`

## Batch168 components

- `manifests/SKCM_BATCH62_FINAL_EXACT_TARGETS.json`
- `START_B168_PRODUCTION_WITH_BATCH62_SKCM.cmd`
- `.github/workflows/batch168-production.yml`
- `reports/BATCH168_REPORT.md`

## Battle/static recovery baseline retained

Batch165 independently executed the retained `ST2R41_CD1_MASTER_BUILD_V29.zip` sparse package against the exact pristine Disc 1 and passed:

- original-sector Expected Write: `609/609`
- patched-sector SHA-256: `609/609`
- original and patched MODE1/2352 EDC/ECC: `609/609`
- unregistered changed sectors: `0`
- candidate Disc SHA-256: `8ceff2afb22e080469ad1adcc8f84f85d45c6b5e838df101beba70f00e3b0861`
- whole-asset re-extraction: `21/21`

The 21 recovered assets remain within the established 39/58 physical byte scope and do not inflate that count.

## Mandatory safety policy

- no package Python execution for untrusted retained packages;
- no estimated or inferred game bytes;
- exact pristine Disc SHA-256 required;
- exact per-asset source SHA-256 Expected Write required;
- exact replacement size and SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q required;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no game, font, asset, movie or full Disc bytes committed to GitHub.

## Next work

Continue executable sparse-package recovery outside the proven 39/58 battle/static physical scope, prioritizing exact payload recovery for the remaining 19 static assets and retaining the 58/58 historical SHA certificate as the acceptance gate.
