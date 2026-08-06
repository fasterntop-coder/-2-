# Batch 209 — Final required raw-sector composition gate

## Completed

- Added `tools/finalize_cd1_with_required_raw_sectors.py`.
- The tool consumes the 91-asset candidate produced by Batch205 and exact raw-sector payloads selected only by SHA-256.
- Required-sector LBAs are rejected if they overlap any sector occupied by the 91-asset write plan.
- Each required sector enforces:
  - pristine-sector Expected Write SHA-256,
  - exact replacement SHA-256,
  - MODE1/2352 EDC/ECC before and after writing,
  - post-write sector SHA-256.
- After required-sector composition, all 91 assets are re-extracted and checked against their replacement SHA-256 values.
- Any failure deletes the output Disc.
- Added synthetic CI coverage for MODE1/2352 validity, LBA-range accounting, collision rejection, and manifest structure.

## Safety

- Estimated or guessed payload bytes: **0**
- Repository Disc images: **0**
- Copyrighted sector payloads committed: **0**

## Runtime input still required for a full final BIN

- Batch205 91-asset candidate BIN.
- Raw sector payload for LBA `208689` with SHA-256 `97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0`.

These bytes are accepted only after all exact gates pass.
