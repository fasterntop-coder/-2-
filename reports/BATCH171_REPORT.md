# Batch 171 — Legacy PBOOK raw-sector recovery bridge

## Status

`PASS_TOOLING_COMMITTED_RUNTIME_EXACT_SIDECARS_REQUIRED`

## Completed work

- Added a non-executing AST reader for the historical `batch110_apply_to_original_bin.py` sector contract.
- Locked the exact 29-sector PBOOK subset: PBOOK_BT 12, PBOOK_EC 5, PBOOK_RC 12.
- Added recursive loose-file and ZIP sidecar discovery by exact patched raw-sector SHA-256.
- Added pristine Disc 1 size and SHA-256 discovery.
- Added per-asset source SHA-256 Expected Write checks.
- Added exact reconstruction of all three PBOOK replacement assets.
- Added whole-asset replacement SHA-256 gates.
- Added optional MODE1/2352 Disc candidate creation from the registered exact raw sectors.
- Added changed-sector accounting and 3/3 whole-asset re-extraction gates.
- The historical patcher is parsed with `ast.literal_eval`; it is never imported or executed.

## Exact contract

- pristine Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- PBOOK_BT replacement: `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`
- PBOOK_EC replacement: `378d92a4daf3db00d7c172ae8d233fad1fe3e1452cb979e9bd8b5610220152f5`
- PBOOK_RC replacement: `c5bc0866ea5581f64bccb0a9da1c6baf53c77601fa247469441e49d0eaae4907`
- exact changed raw sectors: `29`

## Runtime gate

A physical output is accepted only when the scan root contains:

1. the exact pristine Disc 1 BIN or a ZIP containing it;
2. `batch110_apply_to_original_bin.py` with a literal 29-sector PBOOK contract;
3. all 29 exact 2,352-byte patched raw-sector sidecars, loose or inside ZIP archives.

No guessed bytes, inferred payload, partial asset, or SHA override is permitted.
