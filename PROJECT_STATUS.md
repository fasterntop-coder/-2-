# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 142 — PASS

PBOOK_BT recovery was corrected from a palette-only reconstruction problem to a verified Batch110 asset-recovery problem.

The target SHA `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe` is the Batch110 independent reconstruction that already passed 36/36 active text, 23/23 non-text preservation, 4/4 hold preservation, 63/63 descriptor roundtrip, EDC/ECC and five-asset re-extraction.

New executable recovery chain:

1. `tools/recover_pbook_bt_b110.py`
2. `manifests/PBOOK_BT_B110_LINEAGE.json`
3. `START_B142_RECOVER_PBOOK_BT.cmd`
4. `reports/BATCH142_REPORT.md`

The scanner recursively searches loose files and ZIP archives for:

- exact 87,712-byte PBOOK_BT source/candidate assets
- raw 659,293,824-byte Disc 1 images containing either asset

It extracts only PBOOK_BT and emits it only when the whole-asset SHA matches the pristine source or verified Batch110 candidate.

## Exact gates

- Pristine PBOOK_BT: `43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64`
- B110 PBOOK_BT: `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe`
- Pristine Disc 1: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- B110 five-asset Disc 1: `c6fc9827ee5d8ae17c918a8d7468faa4769601e13329c7485b3df53d5fd17c14`

## Safety

- No copyrighted game data committed.
- No whole disc image emitted.
- No unverified candidate emitted.
- Palette-transfer inference remains available only as fallback.

## Next

Run the exact recovery scanner against retained local Disc 1/B110/B117/B118 BIN and ZIP material. Once the B110 PBOOK asset is recovered, merge it into the 39-asset exact baseline and regenerate the next SHA-gated BIN/CUE candidate.
