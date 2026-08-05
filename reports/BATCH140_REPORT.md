# ST2R41 Batch 140 — PBOOK multi-level palette-transfer search

## Status

`PASS_PBOOK_PALETTE_TRANSFER_SEARCH_HARNESS_AND_CI`

## Completed

- Added `tools/pbook_palette_transfer_search.py`.
- Added packed 4bpp nibble decode/encode with row-stride preservation.
- Added SHA-256 source, per-region and whole-asset gates.
- Added changed-byte count gates.
- Added multi-level coverage maps and transfer families:
  - replace, max, min
  - saturating add/subtract
  - wrapping add, XOR
  - screen, multiply
  - 15 weighted interpolation families
- Added monotonic active-level LUT enumeration and quantized fallback.
- Candidate output is emitted only when the exact whole-asset target SHA matches.
- Added verified source/target hash manifest for PBOOK_BT, PBOOK_EC and PBOOK_RC.
- Added GitHub Actions compile and synthetic recovery test.

## Verification

GitHub Actions run `31009569947` completed successfully.

The synthetic test proves that a non-linear four-level mask mapping combined with a screen transfer can be recovered through the same enumeration path used by the real search.

## Safety

- No copyrighted game bytes committed.
- No unverified PBOOK candidate emitted.
- Original bytes outside configured descriptor regions remain untouched.
- Exact whole-asset SHA remains the final gate.

## Next execution input

The next search run consumes the existing B139 descriptor geometry, exact Korean glyph masks and per-region SHA/changed-byte gates. The tool then searches the expanded multi-level transfer family and emits a PBOOK asset only on exact SHA closure.
