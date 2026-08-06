# Batch 217 — 91-asset replacement input binding

Status: `PASS_TOOLING_EXACT_REPLACEMENT_BINDING_READY`

## Completed

- Added a strict verifier that binds Batch204 preflight results to the 91-asset exact write plan.
- Requires exactly 91 resolved records and zero missing records.
- Enforces a complete asset-set bijection with no unknown or duplicate assets.
- Rechecks scope, LBA, size and replacement SHA-256 against the write plan.
- Rechecks each loose-file or ZIP-member locator's recorded size and SHA-256.
- Rejects one locator claiming different payload hashes.
- Records digest alias counts without treating identical exact payload bytes as an error.

## Safety

- Estimated payload bytes: 0
- Disc bytes written: 0
- Selection policy: exact size + SHA-256 + plan geometry only
- Downstream gates remain Expected Write, MODE1/2352 EDC/ECC and 91/91 re-extraction.

## Runtime dependency

A real PASS result requires `output/BATCH204_PREFLIGHT_RESULT.json` produced from the File Library inputs with status `PASS_ALL_91_EXACT_INPUTS_READY`.
