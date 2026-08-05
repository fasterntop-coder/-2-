# Batch 144 — Legacy apply-script manifest extraction

## Status

`PASS_LEGACY_APPLY_SCRIPT_AST_EXTRACTION_CI_VERIFIED`

## Completed

- Added `tools/extract_apply_manifest.py`.
- The tool reads historical `batch110_apply_to_original_bin.py`, `batch118_apply_to_original_bin.py` and related scripts without executing them.
- It extracts `SECTORS` / `SEC` / `M` dictionaries through Python AST and `literal_eval` only.
- It normalizes every raw LBA into `st2-exact-sector-manifest-v1` with:
  - asset name
  - patched-sector payload path
  - expected original-sector SHA-256
  - patched-sector SHA-256
  - source and target whole-BIN SHA-256 gates
  - source size and raw-sector size
- Duplicate LBAs, missing hashes and malformed entries fail closed.

## Verification

GitHub Actions run 8 completed successfully. Compilation and the parser self-test passed together with all prior exact recovery, Expected Write and roundtrip tests.

## File Library recovery finding

The full historical B118 apply script remains available in File Library and contains the complete 1,626-sector metadata dictionary, source BIN SHA `d6dba9f9...` and target BIN SHA `75f300e5...`. This metadata can now be converted into a standalone normalized manifest without running legacy code.

The 2,352-byte patched-sector payload bodies or a retained target BIN are still required for actual byte recovery; SHA-256 values alone are not reversible.

## Next

Run the extractor against the retained B118 apply script when it is present on the local filesystem, then feed the normalized manifest directly into `recover_exact_patch_from_manifest.py` for exact payload harvesting and full BIN reconstruction.
