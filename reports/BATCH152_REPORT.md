# Batch 152 — Batch183/187 exact asset recovery

## Completed

- Recorded the later verified SYSTEM, SYS14 and SYS20 exact target lineage.
- Added a scanner for loose assets, raw Disc 1 checkpoint BINs, ZIP-contained assets and ZIP-contained checkpoint BINs.
- Assets are emitted only after complete size and SHA-256 target matches.
- Whole Disc images are never emitted or modified.

## Exact targets

- SYSTEM: `aff08f718bb8186c7162601f76b927dfa516c21139f60fc6d3cf27f8a8a84a58`
- SYS14: `06597ddf3d34f0463e611f796146bb1e80d7e32df1f59925481669969840b92d`
- SYS20: `55e978d10d4f2ca010b77bec0fa205692923f5ab3b5a2c7deeb1c830e3cf5e8c`

## Historical validation anchors

- Batch183 SYSTEM+SYS14 Disc SHA: `4343b8845f7f9cd4725de085e3a779c7c77185c0e6043d99b5d226335b69f5cf`
- Batch187 17-asset Disc SHA: `18e4acbe241319dbd3e29cf0f01628deba13326fb18cc6bcea00fdbc3ab5016f`

## Safety

No bytes are inferred from hashes. A file is retained only when its complete SHA-256 equals the trusted historical target.
