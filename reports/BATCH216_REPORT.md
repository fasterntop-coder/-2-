# ST2R41 Batch 216 — Pristine Expected Write Source Gate

## Status

`PASS_EXPECTED_WRITE_SOURCE_VERIFIER_IMPLEMENTED`

## Completed

- Added a read-only verifier that binds all 91 `source_sha256` values in the exact write plan to bytes re-extracted from the exact pristine Disc 1 image.
- Missing or malformed source hashes are rejected.
- Each operation must preserve exact `lba`, `size`, `user_sectors`, `end_lba_exclusive`, and `EXPECTED_WRITE_EXACT_HASH_ONLY` policy geometry.
- Overlapping operations and Disc-boundary violations are rejected.
- Every pristine source sector read is verified as valid MODE1/2352 with EDC/ECC before hashing.
- Source and replacement SHA-256 values must differ.
- The verifier emits a deterministic 91-record JSON result when run with the pristine Disc.
- Added regression self-tests and GitHub Actions CI.

## Runtime gate

A full 91/91 source-byte result requires the pristine Disc image:

- size: `659293824`
- SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`

Run:

```bash
python tools/verify_cd1_expected_write_sources.py \
  --pristine-disc "/path/to/015 Sakura Taisen 2 Disc 1 of 3 (J).bin" \
  --plan manifests/CD1_EXACT_WRITE_PLAN.json \
  --output output/BATCH216_EXPECTED_WRITE_SOURCES.json
```

## Safety

- Estimated or fabricated game bytes: `0`
- Disc bytes written: `0`
- Exact SHA-256, Expected Write, MODE1/2352 EDC/ECC, and re-extraction policy retained
