# ST2R41 Batch 145 — Multi-checkpoint exact-sector mosaic recovery

## Status

`PASS_MULTI_CHECKPOINT_MOSAIC_RECOVERY_ENGINE`

## Purpose

Recover the complete Batch118 1,626-sector target even when no single retained
B118 BIN or PATCH_SECTORS package survives. Historical checkpoints may each
contribute a different exact subset.

## New executable chain

1. `tools/recover_checkpoint_mosaic.py`
2. `manifests/B118_CHECKPOINT_LINEAGE.json`
3. `START_B145_CHECKPOINT_MOSAIC.cmd`

## Supported recovery sources

- loose 2,352-byte patched-sector files
- 2,352-byte patched-sector members inside ZIP archives
- any 659,293,824-byte loose checkpoint BIN
- any 659,293,824-byte checkpoint BIN inside a ZIP archive
- the exact pristine Disc 1 BIN for final application

Known high-value checkpoints include:

- B110: five assets
- B117: 56 assets / 1,568 target sectors
- B124: SYSTEM and SYS14 / 58 target sectors
- B127: 25 assets / 727 target sectors
- B130: 33 assets / 960 target sectors
- B118: full 58 assets / 1,626 target sectors

The optimal pair is B117 plus B124: together they can supply all B118 target
sectors even when the full B118 output is absent.

## Acceptance gates

- legacy apply script parsed with AST literals only; never executed
- each accepted payload is exactly one full raw sector
- complete raw-sector SHA-256 must equal the B118 target sector hash
- sector provenance is recorded
- final application requires Expected Write SHA-256 at every source LBA
- final BIN must equal B118 SHA-256
  `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`
- failed output BINs are removed by the underlying exact apply engine
- EDC/ECC is preserved by accepting only byte-exact historical raw sectors that
  belong to the previously audited B118 target

## Output

`MOSAIC_RECOVERY_RESULT.json` includes:

- sector recovery count by source type
- per-asset recovered/total sector coverage
- exact missing LBA list
- checkpoint audit trail
- per-sector provenance
- sparse patch ZIP SHA-256
- final BIN/CUE SHA-256 when all gates pass

## Validation

Synthetic recovery used three disjoint sources:

- one partial loose checkpoint BIN
- one different partial checkpoint BIN inside a ZIP
- one target raw-sector member inside a ZIP

The engine mosaiced all target sectors, applied them to the exact pristine
source, and reproduced the complete expected target byte-for-byte.

GitHub Actions run 10: `SUCCESS`.

## Remaining runtime input

The File Library currently retains manifests, reports and sector hash oracles,
but not the 2,352-byte payload bodies. A retained local checkpoint BIN/ZIP or
PATCH_SECTORS package is still required for real payload harvesting.
