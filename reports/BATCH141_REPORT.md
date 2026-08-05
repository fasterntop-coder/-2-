# ST2R41 Batch 141 — PBOOK_BT 高/低 exact recovery pipeline

## Status

`PASS_EXACT_HEIGHT_LOW_JOB_PIPELINE_READY`

## Recovered historical gates

### Descriptor 3

- Japanese: `高`
- Korean: `높`
- Offset: `0x10280`
- Dimensions: `16x16`
- Original region SHA-256: `6486ec3bd278dc168c5cab2801e151400ac202221fc306395324c52951bd71b8`
- Exact target region SHA-256: `8796fc3d66699132e361a438d9e13fc465195c63a16979c32982555fcf728a2d`
- Exact changed bytes: `72`

### Descriptor 5

- Japanese: `低`
- Korean: `낮`
- Offset: `0x10380`
- Dimensions: `16x16`
- Original region SHA-256: `7c67918af5689864ecd34ba47a487ed449efa72d56597d975af02e59133dbcc9`
- Exact target region SHA-256: `5acee59d5d8cafc9a1197710d5b9593b7bdcb8391ac25d9c2840f83715ffc6f0`
- Exact changed bytes: `78`

## Exact glyph gates

- `높`: `011c18ef5a3845726d0e96e9fcccfb14d5033994759dcab3d02f4fc464bdf3f4`
- `낮`: `d5dba7657013344728fe3d43f5dcd77aaea7850b12f5c46404bfde5d079e35c6`

## Added

- `tools/extract_glyph_by_sha.py`
  - Scans a user-owned Korean SYSTEM/MES asset in 128-byte glyph units.
  - Writes glyph data only on a unique exact SHA match.
- `jobs/PBOOK_BT_HEIGHT_LOW.json`
  - Materialized two exact region SHA gates and the whole PBOOK_BT target gate.
- `tools/run_pbook_bt_height_low.py`
  - Executes glyph extraction, resolved-job creation and palette search as one pipeline.
- `START_PBOOK_BT_B140.cmd`
  - Windows launcher for the end-to-end pipeline.

## Validation

- Glyph extractor synthetic unique-SHA recovery: PASS in GitHub Actions run 2.
- Multi-level transfer synthetic recovery: PASS in GitHub Actions run 2.
- JSON manifests: PASS in GitHub Actions run 2.
- End-to-end runner compilation is covered by GitHub Actions run 3.

## Output rule

`PBOOK_BT_B140_EXACT.CG` is emitted only if both descriptor region hashes and the full target asset SHA-256 match. A changed-byte-count-only hit is never emitted.

## Next

Run the resolved exact job against the pristine PBOOK_BT source and a Korean SYSTEM/MES asset containing the exact glyph hashes. If no exact whole-asset hit is found, promote candidate telemetry to derive a background-dependent 16x16 transfer matrix rather than broadening geometry again.
