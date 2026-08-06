# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Exact battle-bank physical recovery: 55/55
- Exact PBOOK physical recovery: 3/3
- Exact battle/static physical recovery: 58/58
- Historical battle/static certificate: 58/58
- Exact story/movie production scope: 42 assets
- Authoritative workflow: one `main` lineage only; parallel workflows forbidden

## Current batch

### Batch 200 — PASS REAL FULL58 RECOVERY CLOSURE

The complete battle/static scope has now been physically reconstructed from retained real package bytes and a pristine Disc 1 parent. This is no longer a hash-only or future recovery contract.

## Real recovery inputs

- pristine Disc 1 archive: `015 Sakura Taisen 2 Disc 1 of 3 (J) (2)(1).zip`
  - size: `458,507,639`
  - SHA-256: `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- pristine BIN:
  - size: `659,293,824`
  - SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Batch137 55-bank package:
  - SHA-256: `48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c`
- Batch110 PBOOK package:
  - SHA-256: `ed262a52b32c9a326edff85c1d7191ff7b46e3379771d973af536cf06c3103a3`

## Batch200 verified result

- exact battle banks: `55/55`
- exact PBOOK assets: `3/3`
- exact battle/static assets: `58/58`
- changed raw sectors: `1,626`
- unregistered changed sectors: `0`
- sector payload mismatches: `0`
- source-sector Expected Write: PASS `1,626/1,626`
- original MODE1 EDC/ECC: PASS `1,626/1,626`
- patched MODE1 EDC/ECC: PASS `1,626/1,626`
- whole-asset re-extraction: PASS `58/58`
- final Disc SHA-256: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

## Batch200 components

- `tools/recover_real_full58.py`
- `manifests/BATCH200_REAL_FULL58_RECOVERY.json`
- `manifests/SINGLE_LINEAGE_LOCK.json`
- `START_B200_RECOVER_REAL_FULL58.cmd`
- `.github/workflows/batch200-full58-recovery.yml`
- `reports/BATCH200_REPORT.md`

## Single-lineage rule

All future work must fetch the latest `main`, read `PROJECT_STATUS.md` and `manifests/SINGLE_LINEAGE_LOCK.json`, then perform exactly one next task on this lineage. Parallel batches or independent chat-driven writes are forbidden.

## Mandatory safety policy

- no estimated or inferred payload bytes;
- exact pristine Disc SHA-256 required;
- exact source-sector Expected Write SHA-256 required;
- exact package and patched-sector SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q required;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no copyrighted game, font, asset, movie or full Disc bytes committed to GitHub.

## Next production priority

Battle/static recovery is closed at 58/58. Continue the single CD1 production lineage by integrating the already promoted 42 story/movie assets with this exact static baseline, then advance only newly completed story or movie assets toward the CD1 100% candidate.
