# Batch 204 — CD1 exact write input preflight

## Status

`PASS_PREFLIGHT_TOOL_AND_BLOCKER_REPORTING_READY`

## Completed

- Added `tools/preflight_cd1_exact_write_inputs.py`.
- Consumes the deterministic 91-asset `CD1_EXACT_WRITE_PLAN.json`.
- Recursively scans loose files and ZIP members.
- Selects replacement payloads only when both byte size and full SHA-256 match.
- Accepts the pristine Disc only at size `659293824` and SHA-256 `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`.
- Emits exact resolved and missing asset lists in `BATCH204_PREFLIGHT_RESULT.json`.
- Performs no Disc writes and generates no estimated payload bytes.

## Preserved gates

1. Pristine Disc SHA-256.
2. Replacement size and SHA-256.
3. Expected Write before integration.
4. MODE1/2352 EDC/ECC after integration.
5. 91/91 exact re-extraction before acceptance.

## CI

The workflow compiles the tool and verifies that a repository-only scan produces a deterministic blocked result with exactly 91 missing replacement payloads and zero written or generated game bytes.

## Next executable gate

Run the preflight tool against File Library materialized inputs or a local archive root. Integration may begin only after the result is `PASS_ALL_91_EXACT_INPUTS_READY`.
