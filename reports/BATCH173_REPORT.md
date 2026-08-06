# Batch 173 — PBOOK checkpoint BIN sector recovery

## Status

`PASS_CHECKPOINT_BIN_RECOVERY_PATH_IMPLEMENTED`

## Completed work

Batch171 required 29 loose raw-sector sidecars. Batch173 adds a second exact recovery route for retained full Disc checkpoint BINs and BIN entries inside ZIP archives.

The scanner does not trust filenames, package labels, or historical PASS text. It reads only the 29 registered PBOOK LBAs and accepts a sector only when its complete 2,352-byte SHA-256 equals the literal Batch110 patched-sector oracle parsed through AST.

## Acceptance gates

- legacy patcher parsed without import or execution;
- exactly 29 PBOOK target sectors;
- full raw-sector SHA-256 equality;
- independent MODE1/2352 EDC, ECC-P and ECC-Q verification;
- pristine Disc 1 SHA-256 gate before asset reconstruction;
- source whole-asset Expected Write SHA-256;
- replacement whole-asset SHA-256 for PBOOK_BT, PBOOK_EC and PBOOK_RC;
- optional Disc build with changed-sector accounting and 3/3 re-extraction.

## Components

- `tools/recover_pbook_sectors_from_checkpoint_bins.py`
- `START_B173_RECOVER_PBOOK_FROM_CHECKPOINT_BINS.cmd`
- `.github/workflows/batch173-pbook-checkpoint-recovery.yml`

## Runtime requirement

A physical recovery requires a pristine Disc 1 BIN and one or more retained 659,293,824-byte checkpoint BINs containing all 29 exact registered patched PBOOK sectors. Checkpoints may be loose or stored inside ZIP archives.

No game or asset bytes are committed to GitHub.
