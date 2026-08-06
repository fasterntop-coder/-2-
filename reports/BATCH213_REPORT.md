# Batch 213 — Strict 91-asset re-extraction record gate

## Completed

- Added an independent validator for the 91 per-asset re-extraction records.
- Rejects every non-object asset entry instead of silently skipping it.
- Requires exactly 91 unique asset names.
- Requires exact `PASS` on every record.
- Requires a lowercase 64-character SHA-256 on every record.
- Added a regression self-test that inserts a string into the 91-entry list and requires rejection.

## Safety gates

- No estimated bytes are generated.
- No Disc bytes are written.
- Existing SHA-256, Expected Write, MODE1/2352 EDC/ECC and full re-extraction gates remain unchanged.

## Files

- `tools/verify_cd1_reextraction_asset_records.py`
- `.github/workflows/batch213-strict-reextraction-records.yml`
