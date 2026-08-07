# Batch 228 — CD1 exact51 promotion and overall-progress correction

## Completed

- Promoted the exact static/battle recovery baseline from 45/58 to 51/58.
- Added B112 banks: SYS33, SYS27, SYS31, SYS34, SYS04, SYS29.
- Preserved the B112 evidence gate: 1,374 records, zero LBA conflicts, MODE1/2352 EDC/ECC PASS, 13/13 historical re-extraction PASS.
- Added exact candidate SHA-256 values for all six promoted assets.
- Added a hard gate preventing the CD1 overall patch rate from being reported as 70% until story, movie and UI/static assets are present in one validated Disc 1 candidate and the official runtime implementation ledger reaches 70.0%.

## Current honest project indicators

- Official CD1 runtime implementation record: 46.3%.
- Official CD1 hardware-confirmed record: 44.4%.
- Story offline candidate: 14,865/14,875.
- Movie static inventory: 24/24.
- Exact battle/static recovery: 51/58 (87.9%).

These component candidate rates are not interchangeable with the overall playable patch percentage.

## Safety

- Estimated bytes: 0.
- Expected Write policy retained.
- SHA-256 binding retained.
- EDC/ECC and re-extraction gates retained.
- No Disc image committed.

## Next actual work

Recover and promote B111/B110/B109 exact payloads to 58/58, then compose story, movie and UI/static payloads into a single Disc 1 candidate. Only that unified candidate can raise the official overall implementation percentage toward 70%.
