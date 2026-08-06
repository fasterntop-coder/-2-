# Batch 223 — SYS22 exact archive recovery path

## Completed

- Fixed `SYS22` as the next exact CD1 integration target.
- Registered exact geometry and hashes:
  - LBA `207446`
  - size `82,030`
  - pristine SHA-256 `e28752f3b6d6e1fe4299adbbd444e6df4e2d1c617a1e3e6e7edf4ea897288d24`
  - replacement SHA-256 `d4bbcd86442f82295afd1631548a56030e0c791e74477b3ac96e31fb2db6c976`
- Added an AST-only reader for the archived Batch116 apply script. The legacy script is never executed.
- Added archive recovery for exact 2,352-byte patched sectors from loose files, ZIP members, and checkpoint BIN/IMG files.
- The tool emits the asset only after all 29 sector SHA-256 oracles and the final whole-asset SHA-256 pass.
- No inferred bytes are generated and no Disc image is modified.

## Added

- `tools/recover_next_exact_asset_from_archives.py`
- `manifests/SYS22_NEXT_EXACT_TARGET.json`

## Current candidate baseline

- Actual integrated static assets: `21/58`
- Explicit candidate re-extraction: `23/23 PASS`
- Next promotion target: `SYS22` (`22/58` after successful payload recovery and Disc integration)
