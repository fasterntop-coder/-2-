# Batch 202 — CD1 cross-manifest boundary gate

## Status

`PASS_CD1_MANIFEST_BOUNDARY_AUDIT`

GitHub Actions run `31095190253` completed successfully on 2026-08-06.

## Completed work

Added `tools/audit_cd1_manifest_boundaries.py` and a mandatory CI path gate for the two current production manifests:

- `manifests/BATCH200_REAL_FULL58_RECOVERY.json`
- `manifests/CD1_PRODUCTION_STORY_MOVIE_TARGETS.json`

The gate verifies, without reading or writing copyrighted Disc bytes:

- canonical Disc 1 size and SHA-256;
- MODE1/2352 and 2,048-byte user-sector geometry;
- strict lowercase SHA-256 syntax;
- declared and actual asset counts;
- 58/58 static asset scope;
- 33 production story/movie assets (30 story + 3 movie);
- production group counts;
- unique asset names and ISO paths;
- user-data sector spans and Disc bounds;
- no LBA overlap inside either manifest;
- no LBA overlap between the 58 static assets and 33 production assets;
- Batch200 1,626 changed-sector accounting;
- zero unregistered sectors and zero payload mismatches;
- retained `58/58 PASS` re-extraction gate.

## Safety

- Disc bytes written: `0`
- Estimated or generated patch payload bytes: `0`
- No inferred bytes accepted
- Existing Expected Write, EDC/ECC, SHA-256 and re-extraction gates remain unchanged

## Commits

- Tool: `914b4f2e91510f8e9342e3ffc707de4cd46395c9`
- CI: `79f535c20816a228178db04e163040d4a8411aba`
