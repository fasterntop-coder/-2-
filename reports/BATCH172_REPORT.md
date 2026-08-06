# Batch 172 — Computed MODE1/2352 PBOOK EDC/ECC gate

## Status

`PASS_INDEPENDENT_EDC_ECC_VERIFIER_AND_29_SECTOR_AUDIT_READY`

## Completed

- Added a standalone MODE1/2352 verifier that computes EDC, ECC-P and ECC-Q from sector bytes.
- Added a Batch171 companion audit for the exact 29 PBOOK sectors.
- The audit parses the historical Batch110 literal sector map without executing legacy code.
- Every original sector must match its registered SHA-256 Expected Write value.
- Every patched sector must match its registered patched SHA-256 value.
- Original and patched sectors are each independently checked for sync, mode, EDC, reserved bytes, ECC-P and ECC-Q.
- Registered unchanged sectors are rejected.
- Exact sector counts are locked to BT 12, EC 5 and RC 12.
- A machine-readable per-sector JSON audit is emitted only after all gates pass.

## Files

- `tools/mode1_2352.py`
- `tools/audit_batch171_pbook_edc_ecc.py`
- `.github/workflows/batch172-pbook-computed-edc-ecc.yml`

## Runtime input

A full 29/29 audit still requires the exact Batch110 patched raw-sector sidecars and pristine Disc 1 BIN. No estimated bytes are accepted and no game bytes are committed.
