# Batch 154 — Story and Movie Production Integration

## Status

`PASS_PRODUCTION_TOOLCHAIN_READY`

Batch 154 changes the active direction from repeated recovery-only analysis to an executable Korean production path.

## Exact production scope

The retained historical replacement manifests are consolidated into one exact 33-asset scope:

- Batch 51 story MES: 9 assets
- Batch 52 story MES: 18 assets
- Batch 62 SKCM story/system dialogue: 3 assets
- Batch 64 subtitled movies: 3 CAK assets / 33 subtitle events

Totals:

- story assets: 30
- movie assets: 3
- exact replacement assets: 33

## New components

- `manifests/CD1_PRODUCTION_STORY_MOVIE_TARGETS.json`
- `tools/recover_integrate_production_assets.py`
- `START_B154_PRODUCTION_INTEGRATION.cmd`

## Production behavior

The builder scans local retained material for exact replacements in:

- loose MES, BIN and CAK files
- ZIP archive members
- full 659,293,824-byte MODE1/2352 checkpoint images

A replacement is accepted only when both its complete file size and SHA-256 match the trusted historical manifest.

When the exact pristine Disc 1 is present, the builder:

1. verifies the full source BIN size and SHA-256;
2. verifies the original asset SHA-256 before every write (`Expected Write`);
3. inserts only recovered exact replacement bytes;
4. rebuilds MODE1 EDC, ECC-P and ECC-Q for each changed sector;
5. audits the complete changed-sector set for undeclared changes;
6. re-extracts every applied asset and verifies its replacement SHA-256;
7. emits a BIN/CUE candidate, result JSON and sparse raw-sector patch ZIP.

Partial production candidates are allowed only for exact recovered assets. Guessed, synthesized or hash-inverted game bytes are never accepted.

## Safety

- source Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- no game or translated asset bytes committed to GitHub
- no write without source whole-asset SHA match
- no retained output after failed EDC/ECC, changed-sector audit or re-extraction
- all generated patch payloads remain local

## Current execution dependency

The toolchain is complete. A real candidate requires the exact replacement assets themselves, or a retained checkpoint BIN/ZIP containing them, together with the exact pristine Disc 1 BIN.
