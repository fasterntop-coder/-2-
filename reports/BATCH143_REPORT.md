# ST2R41 Batch 143 — Exact B117/B118 Patch Recovery Engine

## Status

`PASS_GENERIC_EXACT_PATCH_RECOVERY_ENGINE_CI_VERIFIED`

## Completed

- Added `tools/recover_exact_patch_from_manifest.py`.
- Added `START_B118_EXACT_RECOVERY.cmd`.
- Historical apply scripts are parsed with Python AST and never executed.
- Supports B117 1,568-sector and B118 1,626-sector manifests.
- Recovers exact sector payloads from loose files or a whole historical output BIN/ZIP.
- Validates every original LBA with Expected Write SHA-256.
- Validates every recovered 2,352-byte payload SHA-256.
- Creates a sparse exact-sector patch ZIP.
- Creates a new full BIN only when the pristine source image is present.
- Deletes a failed output if the whole target BIN SHA-256 does not match.

## B118 gates

- Source BIN SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Target BIN SHA-256: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`
- Changed sectors: 1,626
- Static battle banks: 55/55
- Static battle records: 12,595/12,595

## Verification

GitHub Actions run 6 passed compilation, synthetic manifest parsing, exact sector harvesting, Expected Write application and whole-output byte-exact roundtrip.

## Remaining external input

The exact B117/B118 patched sector bytes or an exact historical B117/B118 full BIN are not present in File Library. The recovery engine is ready to process them immediately when found in a retained local BIN/ZIP/archive.
