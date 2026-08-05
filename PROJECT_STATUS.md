# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 140 — PASS

Implemented and CI-verified an exact SHA-gated 4bpp multi-level palette-transfer search harness for:

- PBOOK_BT
- PBOOK_EC
- PBOOK_RC

New repository assets:

- `tools/pbook_palette_transfer_search.py`
- `manifests/PBOOK_TARGETS.json`
- `.github/workflows/pbook-search-selftest.yml`
- `reports/BATCH140_REPORT.md`

GitHub Actions self-test run `31009569947`: **SUCCESS**

## Active blocker

The real search still requires the existing B139 descriptor geometry, exact Korean glyph-mask binaries and per-region SHA/changed-byte gates to be materialized as local job manifests. No unverified asset is emitted.

## Next

Materialize B139 PBOOK descriptor jobs, execute expanded multi-level LUT/transfer search, close per-region SHA gates, then close whole-asset SHA for PBOOK_BT / PBOOK_EC / PBOOK_RC.
