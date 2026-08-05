# Batch 147 — B118 legacy sidecar schema compatibility

## Status

PASS_TOOLCHAIN_VALIDATED

## Defect corrected

The Batch 146 sidecar recovery tool accepted only a synthetic `decoded_korean`
column. The retained File Library CSV uses the historical columns
`expected`, `decoded`, and `status`, so the real sidecar would have been
rejected despite containing the required data.

## Changes

- Canonicalize historical Reverse Decode aliases.
- Accept the actual `expected/decoded/status` schema.
- Require `expected == decoded` for all 445 translated rows.
- Require `PASS` when a status column is present.
- Preserve a canonical `decoded_korean` output field for downstream tools.
- Require exact bank splits: SYSTEM 222 and SYS14 223.
- Require Record Audit bank splits: SYSTEM 229 and SYS14 229.
- Require complete record coverage 0 through 228 for both audited banks.
- Require valid 64-character hexadecimal source and candidate record SHA-256 values.
- Keep Reverse Decode keys as a strict subset of the audited record keys.

## File Library grounding

The retained sources identify:

- `BATCH118_REVERSE_DECODE.csv`: 445 rows, SYSTEM 222 / SYS14 223.
- `BATCH118_RECORD_AUDIT_458.csv`: 458 rows, SYSTEM 229 / SYS14 229.
- Reverse Decode historical header: `index,bank,record,type,expected,decoded,status`.
- Record Audit historical source/candidate SHA fields.

No game bytes or copyrighted sidecar rows are stored in this repository.

## Validation

GitHub Actions run 17 passed all tool compilation and exact-recovery self-tests,
including the new historical-header sidecar roundtrip.

## Safety

- No guessed bytes.
- No game asset output.
- No legacy workbook macro or script execution.
- Sidecars are emitted only after structural, textual, record-coverage and SHA-format gates pass.

## Next gate

Run the corrected tool against locally mounted copies of the two exact File
Library CSVs, then feed the normalized outputs into the SYSTEM/SYS14 exact
compiler. Final acceptance still requires the historical whole-asset SHA gates,
58-sector Expected Write and EDC/ECC checks, 2/2 re-extraction, and the exact
verification BIN/CUE SHA gates.
