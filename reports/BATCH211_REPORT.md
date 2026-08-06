# Batch 211 — CD1 Release Certificate Gate

## Completed

Added a deterministic release-certificate builder that binds the final candidate BIN to all completed safety evidence:

- exact 91-asset write plan
- required legacy raw-sector verification
- full-disc changed-LBA scope audit
- candidate Disc size and SHA-256
- Expected Write
- MODE1/2352 EDC/ECC
- 91/91 asset re-extraction

Each input JSON is itself hashed into the certificate. A report cannot be replaced or edited later without changing the certificate input digest.

## Safety behavior

- Rejects any non-PASS gate.
- Rejects a write plan other than the exact 91-asset plan.
- Rejects a source Disc identity other than size 659,293,824 and SHA-256 `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`.
- Rejects candidate size mismatch.
- Rejects candidate SHA disagreement between gate reports and the supplied BIN.
- Rejects re-extraction results other than 91/91 when counts are present.
- Reads no game payload except hashing the supplied candidate.
- Writes no Disc bytes and generates no estimated payload bytes.

## Added

- `tools/build_cd1_release_certificate.py`
- `.github/workflows/batch211-cd1-release-certificate.yml`

## Current boundary

The builder is ready. A real release certificate is emitted only after an exact 91-asset candidate BIN, required-sector PASS result, and Batch210 full-disc scope PASS result exist for the same candidate SHA-256.
