# Batch 164 — SK0502 exact production promotion

Status: `PASS_MANIFEST_AND_EXECUTION_PATH_CREATED`

## Promoted asset

- ISO path: `SAKURA1/SK0502.BIN`
- LBA: `45825`
- size: `107920`
- source SHA-256: `8fb80c1353d9ceef632fc7198cf8e8ef045f41f08adcc43dbf7cbb9262273ea4`
- replacement SHA-256: `0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc`
- records reviewed: `518/518`
- translated records: `517`
- control records preserved: `1`
- FFFD special controls preserved: `15/15`
- capacity overflow: `0`
- line overflow: `0`
- Japanese remaining: `0`
- reverse-decode mismatches: `0`
- offline validation: `PASS`

## Production scope

- previous exact production assets: `36`
- newly promoted assets: `1`
- current exact production assets: `37`
- story assets: `34`
- movie assets: `3`
- subtitle events: `33`

## Safety gates

The launcher preserves the existing pristine Disc SHA-256, per-asset Expected Write source SHA-256, replacement size/SHA-256, MODE1/2352 EDC/ECC regeneration, changed-sector accounting, and exact re-extraction gates. No inferred payload bytes are accepted.
