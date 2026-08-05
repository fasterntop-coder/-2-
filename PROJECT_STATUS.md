# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 152 — PASS

Later File Library checkpoints prove exact post-B151 outputs for SYSTEM, SYS14 and SYS20. The repository now has an executable recovery path for those exact assets.

## New components

- `manifests/BATCH183_187_EXACT_TARGETS.json`
- `tools/recover_exact_assets_from_checkpoints.py`
- `START_B152_RECOVER_BATCH183_187_ASSETS.cmd`
- `reports/BATCH152_REPORT.md`

## Exact assets

- SYSTEM target: `aff08f718bb8186c7162601f76b927dfa516c21139f60fc6d3cf27f8a8a84a58`
- SYS14 target: `06597ddf3d34f0463e611f796146bb1e80d7e32df1f59925481669969840b92d`
- SYS20 target: `55e978d10d4f2ca010b77bec0fa205692923f5ab3b5a2c7deeb1c830e3cf5e8c`

## Historical checkpoint gates

- Batch183 SYSTEM+SYS14 Disc SHA: `4343b8845f7f9cd4725de085e3a779c7c77185c0e6043d99b5d226335b69f5cf`
- Batch183 changed sectors: 58; MODE1/2352 EDC/ECC 58/58 PASS; re-extraction 2/2 PASS
- Batch187 17-asset Disc SHA: `18e4acbe241319dbd3e29cf0f01628deba13326fb18cc6bcea00fdbc3ab5016f`
- Batch187 changed sectors: 493; MODE1/2352 EDC/ECC 493/493 PASS; re-extraction 17/17 PASS

## Recovery behavior

The scanner recursively inspects:

- loose exact MES assets
- loose 659,293,824-byte checkpoint BINs
- assets inside ZIP archives
- checkpoint BINs inside ZIP archives

Only complete size + SHA-256 target matches are emitted. Whole Disc images are never copied or modified.

## Safety

- No game, font or glyph bytes committed.
- No guessed asset or sector bytes accepted.
- Exact target SHA-256 is required before output.
- Existing Expected Write, EDC/ECC, re-extraction and whole-disc historical gates remain authoritative.

## Active execution input

Run the Batch152 scanner against retained local BIN/ZIP/archive folders. Any recovered SYSTEM, SYS14 or SYS20 becomes an exact reusable asset for the cumulative Disc 1 integration path.
