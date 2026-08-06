# ST2R41 Batch 214 — Plan/Re-extraction Bijection Gate

## Status

`PASS_91_ASSET_PLAN_REEXTRACTION_BIJECTION_TOOL_READY`

## Completed

- Added a strict one-to-one verifier between `CD1_EXACT_WRITE_PLAN.json` operations and the 91 re-extraction records in the scope audit.
- Requires exactly 91 object records on both sides.
- Rejects missing, extra, duplicate, renamed, or non-object asset records.
- Requires every re-extraction record to carry exact `PASS` status.
- Requires each re-extracted replacement SHA-256 to equal the corresponding write-plan replacement SHA-256.
- Added regression tests for asset substitution and hash substitution.
- Added GitHub Actions self-test coverage.

## Safety

- Estimated or generated payload bytes: `0`
- Disc bytes written: `0`
- No copyrighted payload or Disc image committed.

## Next gate

Run this verifier against the real 91-asset scope audit and bind its result into the release-certificate verification chain before hardware validation.
