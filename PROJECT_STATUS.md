# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 153 — PASS TOOLCHAIN

The recovery path now covers the complete historical B118 58-asset census, and a raw MODE1/2352 extraction defect in the Batch152 checkpoint scanner has been corrected.

## New and corrected components

- `tools/extract_b118_assets_manifest.py`
- corrected `tools/recover_exact_assets_from_checkpoints.py`
- `START_B153_RECOVER_ALL_58_ASSETS.cmd`
- `reports/BATCH153_REPORT.md`

## B118 workbook manifest gate

The extractor reads the retained workbook `Assets 58` worksheet and emits a normalized recovery manifest only after all of these pass:

- exact workbook SHA-256: `e8c85862c10b6d30ed21156b17ca93be834c5cb5f76cf1f58d97c1db6ca22ce9`
- exactly 58 expected assets and indexes 0–57
- unique asset names and starting LBAs
- valid original and candidate whole-asset SHA-256 values
- changed-LBA count matches every row
- no changed-LBA overlap or declared LBA conflict
- exactly 1,626 unique changed raw sectors

## MODE1/2352 correction

Checkpoint assets are no longer read as one contiguous raw byte range from `LBA × 2352`.

Each asset is now reconstructed from the 2,048-byte user-data area at raw-sector offsets `16..2063` for every sector. MODE1 sync and mode byte are checked before extraction. This prevents sector headers, EDC, ECC-P and ECC-Q bytes from contaminating recovered assets.

## Recovery behavior

The Batch153 launcher:

1. validates and normalizes the B118 workbook into a 58-asset manifest;
2. scans loose exact `.MES` and `.CG` assets;
3. scans loose checkpoint BINs;
4. scans assets and checkpoint BINs inside ZIP archives;
5. emits an asset only when its complete size and target SHA-256 match.

Whole Disc images are never copied or modified.

## Safety gates

- No game, workbook, font or glyph bytes committed.
- No hash inversion or estimated payload generation.
- Exact whole-asset SHA-256 required for recovered output.
- Expected Write, EDC/ECC, re-extraction and final whole-disc SHA remain mandatory before cumulative patch acceptance.

## Next

Run Batch153 against retained local B110–B152 archive folders. Reconcile recovered assets against the existing 39/58 exact scope, preserve per-asset provenance, and promote any newly recovered exact targets into the cumulative integration vault.
