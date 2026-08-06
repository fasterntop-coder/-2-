# Batch 218 — Bound replacement materialization

## Result

Added a deterministic staging tool for the 91 Disc 1 replacement payloads selected and bound by Batch217.

## New gate

`tools/materialize_cd1_bound_replacements.py`

The tool:

- accepts only a complete `PASS_91_OF_91_REPLACEMENT_INPUT_BINDING` result;
- reopens every loose file or ZIP member instead of trusting cached preflight metadata;
- rejects input-root escapes and unsafe ZIP member paths;
- verifies the bound byte size and SHA-256 before staging;
- writes each payload into a temporary directory and verifies size and SHA-256 again after writing;
- atomically replaces the final staging directory only after all 91 assets pass;
- removes partial temporary output after any failure;
- emits `BATCH218_MATERIALIZED_REPLACEMENTS.json` with one verified record per asset;
- never opens or writes the Disc image.

## Regression coverage

`.github/workflows/batch218-bound-replacement-materialization.yml`

The workflow builds a synthetic 91-asset binding, requires all 91 staged payloads to pass, then mutates one source after binding and confirms that materialization fails without publishing a staging directory.

## Safety state

- Estimated or inferred payload bytes: **0**
- Disc bytes written: **0**
- SHA-256 gate: **preserved and rechecked before/after staging**
- Expected Write gate: **preserved for the apply phase**
- MODE1/2352 EDC/ECC gate: **preserved for the apply/finalization phase**
- 91/91 re-extraction gate: **preserved**

## Next executable step

Bind the exact write-plan applicator to the Batch218 staging manifest so it can consume only the re-read, post-write-verified payload set before Expected Write and raw-sector EDC/ECC processing.
