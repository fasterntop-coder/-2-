# Batch 208 — Permanent legacy-sector preservation gate

## Status

`PASS_LBA208689_PROMOTED_TO_REQUIRED_BUILD_GATE`

## Completed

- Added an exact manifest for required raw sector LBA 208689.
- Fixed the pristine and required sector SHA-256 values from the Batch207 byte-proven replay.
- Added a verifier that validates the manifest on every run and optionally checks a candidate MODE1/2352 BIN directly.
- Added GitHub Actions coverage so future changes cannot silently remove or weaken the gate.

## Required values

- LBA: `208689`
- Raw sector size: `2352`
- Pristine SHA-256: `3da035f48eb2cdd51b4248b5881b1fe2f30f0779234ce553eca7387286df0246`
- Required patched SHA-256: `97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0`

## Safety

Expected Write, MODE1/2352 EDC/ECC, post-build sector hashing and zero estimated bytes remain mandatory. No copyrighted payload or full BIN is committed.
