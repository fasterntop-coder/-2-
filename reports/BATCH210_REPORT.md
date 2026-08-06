# Batch 210 — CD1 candidate full-disc write-scope gate

## Status

`PASS_TOOLING_READY_NO_DISC_BYTES_COMMITTED`

## Completed

- Added `tools/audit_cd1_candidate_write_scope.py`.
- The pristine Disc is accepted only at exactly 659,293,824 bytes and SHA-256 `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`.
- Every MODE1/2352 raw sector is compared between the pristine Disc and a 91-asset candidate.
- Any changed LBA outside the exact 91-asset write-plan ranges aborts the audit.
- Every changed candidate sector must pass EDC, reserved-area, ECC-P, and ECC-Q verification.
- All 91 assets are re-extracted from the candidate and matched to their replacement SHA-256 values.
- The ordered changed-LBA list is itself SHA-256 recorded for deterministic provenance.
- The auditor writes no Disc bytes and generates no estimated payload bytes.

## Why this gate is required

The Batch205 writer and Batch209 finalizer verify the declared assets, but asset re-extraction alone cannot prove that unrelated sectors were not changed. Batch210 closes that gap by comparing the entire candidate Disc against the immutable pristine Disc before required legacy sectors are composed.

## Required production order

1. Build the 91-asset candidate with Batch205.
2. Run Batch210 against the pristine Disc and candidate.
3. Only after Batch210 passes, compose required legacy raw sectors with Batch209.
4. Re-run required-sector and 91/91 re-extraction gates.

## Binary status

No copyrighted Disc image or replacement payload is committed.
