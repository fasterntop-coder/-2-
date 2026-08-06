# Batch 206 — Exact cumulative runtime replay

## Status

`PASS_BATCH60_CUMULATIVE_RUNTIME_REPLAY_EXACT`

## Actual execution

The exact pristine Disc 1 ZIP from File Library was materialized and its BIN was extracted.
The cumulative Batch60 range-patch package was also materialized and executed against that pristine BIN.

- pristine BIN size: `659293824`
- pristine BIN SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- replay output size: `659293824`
- replay output SHA-256: `7f57743b947704963290e2e108485262c940690c4a3c8d60800a7ae3338f397d`
- package expected output SHA-256: identical

## Verified package gates

- payload ranges: `115`
- Batch60 newly changed sectors: `3448`
- cumulative changed sectors: `59051`
- MODE1/2352 EDC/ECC certificate: `59051/59051 PASS`
- independent replay certificate: `PASS`
- SK0306 message roundtrip: `78/78 PASS`
- SK2MV_05 subtitle events: `3`
- ADX packets preserved byte-identical: `110`

No estimated bytes were introduced. The full copyrighted output BIN was deleted after SHA verification and was not committed or retained.
