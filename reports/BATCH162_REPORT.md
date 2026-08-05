# Batch 162 — SK0504 exact production promotion

## Status

PASS_EXACT_SK0504_PRODUCTION_TARGET_ADDED

## New exact asset

- ISO path: `SAKURA1/SK0504.BIN`
- LBA: `45926`
- size: `127140`
- source SHA-256: `52d5429c1d0e4029406d63f9b780bda3d78bb3de90233d4e5de488d2713d07bb`
- Korean replacement SHA-256: `619bee36d6e821665df9e09a0b0ffa36021b58fdbda0c3fbf0f81a9e7421f4ac`

## Translation and structural gates

- records reviewed: 726/726
- translated text records: 725
- control records preserved: 1
- confirmed reuse records: 75
- new translation records: 650
- capacity overflow: 0
- line overflow: 0
- Japanese remaining in Korean text: 0
- reverse-decode mismatches: 0
- file size unchanged: 127140 bytes
- validation: PASS_OFFLINE

## Production scope

The production composer now combines:

- existing story/movie targets: 33 assets
- SK0403 final: 1 asset
- SK0504 final: 1 asset

Combined scope:

- exact production assets: 35
- story assets: 32
- movie assets: 3
- subtitle events: 33

## Safety

No game or translated payload bytes are committed. The launcher accepts only complete replacement files whose size and whole-file SHA-256 match. Disc application remains gated by pristine Disc SHA-256, per-asset Expected Write, MODE1/2352 EDC/ECC regeneration, changed-sector accounting and exact re-extraction.
