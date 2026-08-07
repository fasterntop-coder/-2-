# Batch 226 — CD1 exact 39-asset baseline recovery

## Result

`PASS_EXACT39_BASELINE_RECOVERED`

The previously active `21/58` static baseline was stale. File Library evidence from `BATCH132_RECOVERY_STATUS.xlsx` was re-read directly and promoted to the repository as the current exact baseline.

## Verified historical candidate

- Source Disc 1 size: `659,293,824`
- Source Disc 1 SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Exact assets: `39/58`
- Changed raw sectors: `1,134`
- MODE1/2352 EDC/ECC: `PASS`
- Re-extraction: `39/39 PASS`
- Historical candidate BIN SHA-256: `518c73a08e367a7f36c49a074ec7a91f61007456c99e4e30e73f8bb64575b250`

## B116 correction

All nine B116 banks were already exact and must not be treated as missing:

`SYS20`, `SYS47`, `STNSYS02`, `SYS21`, `STNSYS03`, `SYS23`, `SYS24`, `SYS22`, `SYS25`

This supersedes the Batch224 conclusion that SYS22 payload alone blocked progress.

## Added

- `tools/extract_cd1_exact39_from_b132_workbook.py`
- `manifests/CD1_EXACT39_BASELINE.json`

The extractor rejects duplicate assets, bad SHA-256 values, non-PASS records, invalid geometry, overlapping extents, missing B116 banks, aggregate count mismatch, failed EDC/ECC, failed re-extraction, or an unexpected historical candidate BIN SHA.

No guessed bytes were generated and no Disc image was committed.

## Next exact recovery order

1. B113 six banks: `SYS03`, `SYS02`, `SYS05`, `SYS08`, `SYS17`, `SYS07` → `45/58`
2. B112 six banks → `51/58`
3. B111 `SYS00`, `SYS01` → `53/58`
4. B110/B109 `STNSYS00`, `SYS26`, `PBOOK_BT`, `PBOOK_EC`, `PBOOK_RC` → `58/58`
