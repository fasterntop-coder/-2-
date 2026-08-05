# ST2R41 Batch 153 — B118 58-asset manifest and correct MODE1 recovery

## Status

`PASS_TOOLCHAIN_FULL_58_ASSET_RECOVERY_READY`

## Completed

1. Added `tools/extract_b118_assets_manifest.py`.
   - Reads the exact retained B118 workbook without executing macros or external code.
   - Requires workbook SHA-256 `e8c85862c10b6d30ed21156b17ca93be834c5cb5f76cf1f58d97c1db6ca22ce9`.
   - Parses the `Assets 58` worksheet using only Python standard-library ZIP/XML readers.
   - Requires exactly 58 known assets, indexes 0–57, unique names/LBAs, valid original and candidate SHA-256 values, no LBA conflict, and exactly 1,626 unique changed raw-sector LBAs.
   - Produces a normalized manifest only after every gate passes.

2. Corrected `tools/recover_exact_assets_from_checkpoints.py`.
   - The previous implementation read a contiguous byte range beginning at `LBA × 2352`; that incorrectly included raw-sector headers, EDC and ECC bytes after the first 2,048-byte user-data block.
   - The corrected implementation reconstructs each asset from offset 16 through 2063 of every MODE1/2352 sector.
   - MODE1 sync and mode-byte validation are required before any checkpoint sector is accepted.
   - Exact whole-asset size and target SHA-256 remain mandatory.
   - PBOOK assets are emitted as `.CG`; MES banks are emitted as `.MES`.

3. Added `START_B153_RECOVER_ALL_58_ASSETS.cmd`.
   - First extracts the trusted 58-asset manifest from the workbook.
   - Then scans retained loose assets, BIN checkpoints and ZIP archives.
   - Never copies or modifies a whole Disc image.

## Historical gates retained

- Original Disc 1 size: `659293824`
- Original Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- B118 assets: `58`
- B118 changed raw sectors: `1626`
- Raw sector: `2352` bytes
- MODE1 user data: offset `16`, length `2048`

## Safety

- No game, font, workbook or glyph bytes are committed.
- No asset is emitted from workbook metadata alone.
- A recovered asset is written only after complete size and whole-file SHA-256 match.
- Expected Write, EDC/ECC, re-extraction and final whole-disc SHA gates remain required for later integration.

## Next

Run Batch153 against any retained B110–B152 BIN/ZIP/package folders. Recovered exact assets can then be compared with the current 39/58 local scope and promoted into a cumulative, provenance-recorded asset vault. Missing assets remain blocked until their exact bytes are found; hashes are never inverted or approximated.
