# Batch 200 — Real 58/58 Battle/Static Recovery Closure

## Status

`PASS_REAL_FULL58_EXACT_RECOVERY`

Batch200 closes the physical Disc 1 battle/static recovery scope from retained real payloads. It combines the exact Batch137 55-bank delta package with the exact three PBOOK payloads retained in Batch110. No guessed or regenerated game bytes are used.

## Real inputs

- pristine Disc 1 archive SHA-256: `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- pristine BIN SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Batch137 55-asset package SHA-256: `48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c`
- Batch110 PBOOK package SHA-256: `ed262a52b32c9a326edff85c1d7191ff7b46e3379771d973af536cf06c3103a3`

## Verified result

- exact assets: `58/58`
- battle banks: `55/55`
- PBOOK assets: `3/3`
- changed raw sectors: `1,626`
- unregistered changed sectors: `0`
- sector payload mismatches: `0`
- source-sector Expected Write SHA-256: PASS `1,626/1,626`
- original MODE1 EDC/ECC: PASS `1,626/1,626`
- patched MODE1 EDC/ECC: PASS `1,626/1,626`
- whole-asset re-extraction: PASS `58/58`
- exact output Disc SHA-256: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

## New production tool

`tools/recover_real_full58.py` independently parses the retained packages without executing package Python. It validates package hashes, applies the B137 custom deltas and Batch110 raw PBOOK sectors, audits all changed sectors, re-extracts all 58 assets, and deletes the full Disc output by default unless `--keep-disc` is explicitly supplied.

## Repository policy

No game BIN, font, PBOOK, MES, movie, or raw-sector payload bytes are committed. GitHub contains only the deterministic recovery code, hashes, manifests, reports, launcher, and CI contract.
