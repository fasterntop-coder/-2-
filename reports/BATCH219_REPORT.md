# Batch 219 — Materialized Stage Seal

## Completed

Added an independent post-materialization gate for the 91 Disc 1 replacement assets.

- Re-reads every staged payload and verifies exact byte size and SHA-256.
- Requires a complete 1:1 asset set against the 91-asset write plan.
- Rejects missing files, extra files, duplicate names, unknown assets, path aliases, symlinks, directories, and payload drift.
- Binds the Batch218 manifest and write plan by their own SHA-256 values.
- Emits a deterministic `stage_tree_sha256` over the ordered asset, staged filename, size, and payload SHA-256 records.
- Opens and writes no Disc image.

## Preserved gates

- SHA-256
- Expected Write
- MODE1/2352 EDC/ECC
- 91/91 re-extraction

## Files

- `tools/seal_cd1_materialized_stage.py`
- `.github/workflows/batch219-materialized-stage-seal.yml`

## Next executable step

Use only a Batch219 sealed staging tree as the replacement source for final candidate composition, then repeat Expected Write, changed-sector EDC/ECC, full scope audit, and 91/91 re-extraction.
