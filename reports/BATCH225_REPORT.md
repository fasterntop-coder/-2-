# Batch 225 — full-size candidate and common14 exact audit

## Completed

- Rebuilt the B117 common 14-bank candidate from the exact 229-record ledger and 366-slot character map.
- Rebuilt asset SHA-256: `5e89dd92af693ba37e20ab9516d6aca668c8c2a8fd6b480af54ff3b88067efa3`.
- Re-extracted SYS06, SYS28, SYS30, SYS32, SYS35, SYS38, SYS39, SYS40, SYS41, SYS42, SYS43, SYS44, SYS48 and SYS50 from the full-size Batch221 lineage candidate: 14/14 PASS.
- Confirmed these 14 banks were already present in the existing 21-asset candidate, so no duplicate progress credit was applied.

## Defect found

A stale runtime file named `CD1_STATIC21_PLUS_BATCH60.bin` was only `490,488,432` bytes. The valid candidate is exactly `659,293,824` bytes and has SHA-256:

`e335f7e821821191bc7ecf6776b489949dac4dfe0e1ccdea6f7df8217053c6d8`

`tools/verify_cd1_fullsize_static21_candidate.py` now rejects truncated candidates before any asset or release claim and verifies the common 14 banks by re-extraction.

## Gates

- Disc size: PASS
- Candidate SHA-256: PASS
- Common14 rebuild SHA-256: PASS
- Common14 re-extraction: 14/14 PASS
- Estimated bytes: 0
- Disc image committed: no
