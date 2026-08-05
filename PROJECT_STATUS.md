# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 145 — PASS

The B118 recovery path no longer requires one surviving complete B118 BIN or one complete PATCH_SECTORS directory.

A new checkpoint-mosaic engine can combine different exact target sectors from multiple retained historical images and ZIP archives.

## New components

- `tools/recover_checkpoint_mosaic.py`
- `manifests/B118_CHECKPOINT_LINEAGE.json`
- `START_B145_CHECKPOINT_MOSAIC.cmd`
- `reports/BATCH145_REPORT.md`

## Recovery sources

The engine scans:

- loose 2,352-byte sector payloads
- sector payloads stored inside ZIP files
- loose 659,293,824-byte checkpoint BINs
- checkpoint BINs stored inside ZIP files

Each checkpoint may contain only a subset of B118. The tool accepts a sector only when the complete raw-sector SHA-256 matches the trusted B118 manifest target for that LBA.

## Known useful checkpoint lineage

- B110: 5 assets
- B117: 56 assets / 1,568 sectors
- B124: SYSTEM and SYS14 / 58 sectors
- B127: 25 assets / 727 sectors
- B130: 33 assets / 960 sectors
- B118: 58 assets / 1,626 sectors

The highest-value recovery combination is B117 plus B124. Together they can provide all 1,626 B118 target sectors without a retained complete B118 image.

## Exact gates

- Pristine Disc 1 SHA-256:
  `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- B118 output SHA-256:
  `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`
- changed raw sectors: 1,626
- assets: 58
- battle banks: 55/55
- legacy apply script: AST literal parsing only; never executed
- target sector acceptance: complete 2,352-byte SHA-256 match
- final source write: Expected Write SHA-256 required
- final BIN: whole-output SHA-256 required
- EDC/ECC: preserved through byte-exact historical raw-sector hashes

## Outputs

`MOSAIC_RECOVERY_RESULT.json` records:

- recovery count by source type
- per-asset sector coverage
- missing LBA list
- checkpoint audit trail
- per-sector provenance
- sparse patch ZIP hash
- final BIN/CUE hashes when complete

## CI

- GitHub Actions run 10: SUCCESS — multi-checkpoint mosaic roundtrip
- GitHub Actions run 12: SUCCESS — toolchain plus checkpoint lineage manifest validation

The synthetic test recovered disjoint target sectors from a loose checkpoint BIN, a checkpoint BIN inside ZIP, and a loose sector member inside ZIP, then reproduced the expected complete target BIN byte-for-byte.

## Active blocker

File Library contains the B118 apply manifest, checkpoint reports, asset hashes and sector hash oracles, but not the actual 2,352-byte target sector bodies or retained checkpoint BIN bytes.

Real output creation now requires any local retained material containing target bytes, especially one or more of:

- B117 BIN/ZIP
- B124 BIN/ZIP or sparse delta package
- B127/B130 BIN/ZIP
- B118 BIN/ZIP
- any historical PATCH_SECTORS directory or ZIP
- the exact pristine Disc 1 BIN for final application

No sector is reconstructed from hashes or estimates.
