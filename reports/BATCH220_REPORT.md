# Batch 220 — Actual Static21 CD1 Candidate Build

## Status

`PASS_ACTUAL_STATIC21_CD1_CANDIDATE_BUILT_AND_VERIFIED`

## Runtime inputs

- Pristine Disc 1 size: `659,293,824`
- Pristine Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Input package: `ST2R41_CD1_MASTER_BUILD_V29.zip`
- Package SHA-256: `367bfb9e0f921124135c8c80c559c82c60a79de43573ca04a768abf6a251e47c`

## Actual build result

- Candidate Disc SHA-256: `8ceff2afb22e080469ad1adcc8f84f85d45c6b5e838df101beba70f00e3b0861`
- Expected candidate SHA-256: exact match
- Changed raw sectors: `609`
- MODE1/2352 EDC/ECC: `609/609 PASS`
- Re-extracted assets: `21/21 PASS`

## Integrated scope

Actual Disc writes were performed for 21 static assets: `SYSTEM`, `SYS14`, the B117 common banks, `SYS47`, `STNSYS02`, `SYS20`, `SYS21`, and `STNSYS03`.

This is a real build candidate, not a manifest-only result. It is not yet the final CD1 patch: historical static target remains 58 assets and story/movie assets are not integrated in this candidate.

The full copyrighted Disc image was deleted after hashing and re-extraction verification. No guessed bytes were used.
