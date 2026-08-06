# ST2R41 Batch 215 — Plan/Scope Geometry Binding

## Status

`PASS_91_ASSET_PLAN_SCOPE_GEOMETRY_BINDING_GATE_READY`

## Completed

- Added an independent verifier binding the exact 91-asset write-plan file SHA-256 to the scope-audit report.
- Requires exactly 91 unique plan operations and 91 unique re-extraction records.
- Requires per-asset equality for asset identity, LBA, byte size, and replacement SHA-256.
- Rejects substituted write-plan SHA-256 values even when asset names and payload hashes appear valid.
- Added regression tests for LBA substitution, size substitution, and plan-file SHA substitution.
- Added GitHub Actions CI for the regression tests.

## Safety

- Estimated or generated game payload bytes: `0`
- Disc bytes written: `0`
- No inferred bytes were applied.
- Existing Expected Write, SHA-256, MODE1/2352 EDC/ECC, and 91/91 re-extraction gates remain unchanged.

## Files

- `tools/verify_cd1_plan_scope_geometry_binding.py`
- `.github/workflows/batch215-plan-scope-geometry-binding.yml`
- `reports/BATCH215_REPORT.md`
