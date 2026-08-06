# Batch 201 — Exact production asset hash recovery

## Completed

Added a non-inferential recovery scanner for the promoted CD1 story/movie replacements listed in `manifests/CD1_PRODUCTION_STORY_MOVIE_TARGETS.json`.

- scans loose files and ZIP members;
- does not trust filenames;
- accepts payloads only on exact size plus replacement SHA-256;
- supports one exact payload satisfying duplicate-content assets;
- writes recovered assets under their manifest ISO paths;
- re-hashes every written output;
- emits an exact missing-asset list and machine-readable recovery result;
- performs no Disc writes and never generates estimated bytes.

## Current authoritative production manifest

The repository manifest currently contains **33 assets**, not 42:

- story: 30
- movie: 3
- groups: B51_STORY 9, B52_STORY 18, B62_STORY 3, B64_MOVIE 3

Therefore Batch 201 intentionally targets only those 33 registered exact replacements. The remaining nine assets implied by the older “42 assets” status wording are not guessed or synthesized; they require an additional exact manifest containing ISO path, LBA, size, source SHA-256 and replacement SHA-256.

## Files

- `tools/recover_production_assets_by_hash.py`
- `.github/workflows/batch201-production-asset-recovery.yml`

## Runtime gate

A physical 33-asset recovery run requires retained package files containing the exact replacement bytes registered in `CD1_PRODUCTION_STORY_MOVIE_TARGETS.json`. Once recovered, Disc integration must still enforce pristine Disc SHA-256, source Expected Write, MODE1 EDC/ECC, changed-sector accounting and whole-asset re-extraction.
