# Batch 161 — SK0403 Final Production Promotion

## Result

The completed Korean `SAKURA1/SK0403.BIN` from R41 Batch33 is now an exact production target rather than a ledger-only result.

## Exact target

- ISO path: `SAKURA1/SK0403.BIN`
- LBA: `45626`
- size: `113392`
- pristine source SHA-256: `2736d124c75afcf99cf0d8646427ba9478b84215c8de64fb29aa73f7cefa9b1e`
- Korean replacement SHA-256: `94576a14ff92abff690fde9acdd9e5673b834f7d62391be39971f7d70e4932b5`
- records reviewed: `506/506`
- translated text records: `500`
- preserved control/test records: `6`
- reverse decode: `506/506 PASS`
- font slots: `521/566`

## Production scope

`compose_production_manifests.py` combines the existing 33 story/movie targets with SK0403 into a 34-asset production manifest:

- story assets: 31
- movie assets: 3
- subtitle events: 33
- total production assets: 34

The composer rejects source-Disc mismatches, duplicate ISO paths, overlapping extents, invalid sizes/LBAs, and malformed SHA-256 values.

## Build gates

The existing production builder remains authoritative:

1. pristine Disc 1 whole-file SHA-256;
2. per-asset Expected Write source SHA-256;
3. exact replacement size and SHA-256;
4. MODE1/2352 EDC, ECC-P and ECC-Q regeneration;
5. complete changed-sector accounting;
6. exact re-extraction of every applied asset.

No inferred game bytes or translated payload bytes are committed.
