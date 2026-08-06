# Batch 203 — CD1 exact write-plan gate

## Result

Added a deterministic manifest-only integration plan for the verified Disc 1 scopes:

- 58 battle/static assets from `BATCH200_REAL_FULL58_RECOVERY.json`
- 33 story/movie assets from `CD1_PRODUCTION_STORY_MOVIE_TARGETS.json`
- 91 exact hash-addressed asset operations total

## Safety invariants

- Canonical source Disc size and SHA-256 are mandatory.
- Every operation carries an exact replacement SHA-256.
- Story/movie operations additionally carry the exact source SHA-256 and reject source/replacement equality.
- Operations are sorted by LBA and rejected on any intra- or cross-scope overlap.
- Expected Write remains mandatory.
- MODE1/2352 EDC/ECC regeneration and verification remain mandatory after each real write.
- Full re-extraction remains mandatory for all integrated assets.
- The builder reads and writes no copyrighted payload bytes and applies no estimated bytes.

## Added

- `tools/build_cd1_exact_write_plan.py`
- `.github/workflows/batch203-cd1-exact-write-plan.yml`

The CI builds the plan twice and requires byte-identical output before accepting the 91-operation gate.
