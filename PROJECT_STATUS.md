# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- **Core physical/static inventory: 223/223 = 100.0%**
- Story: **141/141**
- Battle/static banks: **58/58**
- Movie static inventory: **24/24**
- Additional exact UI/runtime/title assets on current candidate: **11/11**
- Authoritative workflow: one `main` lineage only; guessed bytes forbidden

## Current authoritative candidate

### Batch 309 — B308 223/223 + exact R39 UI/runtime/title 11

Batch309 keeps the fully closed Batch308 core inventory and physically adds 11 exact assets that were still pristine in Batch308.

- pristine Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Batch308 core-100% SHA-256: `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f`
- **Batch309 Disc SHA-256: `8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01`**
- Disc size: `659,293,824`
- core physical/static inventory: `223/223 PASS`
- supplemental exact R39 assets: `11/11 PASS`
- cumulative changed sectors vs pristine: `90,272`
- all changed-sector MODE1 EDC/ECC: `90,272/90,272 PASS`
- guessed payload bytes: `0`
- third variants accepted: `0`
- outside-footprint changes: `0`

The 11 supplemental assets are:

- battle command UI: `CMD_WIN.CG`
- battle visual UI: `PBOOK_FL.CG`, `PB_EYE.CG`
- battle font: `BTSFONT.BIN`
- runtime low-font banks: `M00LOW.BIN`, `M01LOW.BIN`, `M26LOW.BIN`, `M27LOW.BIN`
- title assets: `TITLE.BIN`, `TTL2CGB.BIN`, `TTL2CGB1.BIN`

`CMD_WIN.CG` is now physically present in the current candidate with SHA-256 `20a4947ce98752681efecffe9a6022dfb324bc9433ece5ce8da6d567f605ee09`, matching the previously validated Korean battle-command texture.

## Physical chain

- Batch240: 94 assets, SHA `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83`
- Batch305: 142 assets, SHA `93b3b08ff5e27f03e056ec3577068a2ae2b91cc3d961fc5628ad79a479a871b1`
- Batch306: 172 assets, SHA `b99a4aebdec0412accf843366fa70b406ccaad1be769fe33b95d81ab36ad4302`
- Batch307: 179/223 = 80.2691%, SHA `137a278985d1659cbf21d106683b50dba092a4d31f198f8dd7cd5573b311909c`
- Batch308: core 223/223 = 100.0%, SHA `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f`
- Batch309: Batch308 + UI/runtime/title 11/11, SHA `8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01`

## Hardware/release status

**Hardware validation is still pending.** Batch309 is the authoritative physical/static candidate, not yet the final hardware-certified public release. Re-encoded subtitle/title-card movies and battle/UI presentation must be playback-tested, and any runtime regression must be corrected without breaking the static safety gates.

## Current production components

- `manifests/CD1_BATCH308_REAL_PHYSICAL_STATIC_223_OF_223.json`
- `reports/BATCH308_REAL_PHYSICAL_STATIC_100_PERCENT.md`
- `tools/verify_batch308_real_physical_static_100.py`
- `manifests/CD1_BATCH309_B308_PLUS_R39_UI_RUNTIME11_PHYSICAL_UNION.json`
- `reports/BATCH309_R39_UI_RUNTIME11_REPORT.md`

## Mandatory safety policy

- no estimated/inferred payload bytes;
- exact source and candidate SHA-256;
- raw-sector Expected Write before writes;
- actual changes only inside approved footprints;
- EDC/ECC on every changed output sector;
- changed-sector accounting;
- exact whole-asset re-extraction;
- identity controls must remain exact where required;
- third variants are blocked unless an explicit newer lineage is proven;
- no copyrighted game/font/movie/full-Disc bytes committed.

## Next production priority

Use Batch309 SHA `8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01` for playback/regression validation. Prioritize battle UI appearance, movie timing/playback, title presentation, runtime crashes and remaining wording/visual defects while preserving all physical gates.
