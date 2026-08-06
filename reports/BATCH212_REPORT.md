# Batch 212 — Independent CD1 Release Certificate Verification

## Status

`PASS_INDEPENDENT_RELEASE_CERTIFICATE_VERIFIER_ADDED`

## Completed

- Added `tools/verify_cd1_release_certificate.py`.
- Added a no-payload synthetic self-test and GitHub Actions workflow.
- Replaced permissive substring-style trust with exact status allowlists.
- Re-hashes and binds all three certificate inputs:
  - 91-asset exact write plan
  - required legacy-sector result
  - full-disc write-scope audit
- Verifies exact candidate SHA-256 agreement between the certificate and scope audit.
- Optionally re-hashes the supplied 659,293,824-byte candidate BIN.
- Requires exact `91/91 PASS` plus 91 individual re-extraction PASS records.
- Rejects `NOT_PASS_*`, `BYPASS_*`, altered input JSON, wrong candidate hashes, and non-exact gate values.

## Safety

- Estimated or generated game payload bytes: `0`
- Disc bytes written: `0`
- No BIN, CUE, replacement payload, font, or copyrighted asset committed.

## Next gated execution

Run the verifier against a completed Batch211 certificate and its exact three bound JSON inputs. Supply the candidate BIN to re-hash the complete Disc image when available.
