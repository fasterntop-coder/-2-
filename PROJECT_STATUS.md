# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 141 — PASS

The PBOOK_BT `高` / `低` descriptors are now connected to an executable exact-recovery pipeline.

Recovered exact gates:

- Descriptor 3 `高 -> 높`: offset `0x10280`, target region SHA `8796fc3d...`, changed bytes `72`
- Descriptor 5 `低 -> 낮`: offset `0x10380`, target region SHA `5acee59d...`, changed bytes `78`
- Whole PBOOK_BT target SHA: `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`

New executable chain:

1. `tools/extract_glyph_by_sha.py`
2. `jobs/PBOOK_BT_HEIGHT_LOW.json`
3. `tools/pbook_palette_transfer_search.py`
4. `tools/run_pbook_bt_height_low.py`
5. `START_PBOOK_BT_B140.cmd`

GitHub Actions:

- Run 1: SUCCESS
- Run 2: SUCCESS
- Run 3: end-to-end runner compile validation initiated

## Safety

- No font file or game asset committed.
- Glyph payloads are extracted locally only on unique exact SHA matches.
- No candidate asset is emitted without both region SHA gates and the whole-asset SHA gate.

## Active execution input

The real run needs a pristine `PBOOK_BT.CG` and one user-owned Korean SYSTEM/MES asset containing the exact `높` and `낮` glyph payloads. The pipeline then performs the expanded multi-level search automatically.

## Next

Execute the real height/low job. If it produces no exact hit, capture candidate telemetry and infer a background-dependent transfer matrix while preserving the proven descriptor geometry.
