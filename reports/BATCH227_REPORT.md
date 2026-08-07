# Batch 227 — CD1 exact45 baseline promotion

## Result

`PASS_EXACT45_BASELINE_PROMOTED`

The verified B132 exact39 baseline was combined with the six non-overlapping B113 banks:

- SYS03
- SYS02
- SYS05
- SYS08
- SYS17
- SYS07

## Coverage

- Previous: 39/58 = 67.2%
- Current: 45/58 = 77.6%
- Delta: +6 assets, +10.4 percentage points

## Evidence gates

- B113 records: 1,374
- B113 new raw sectors: 174
- LBA conflicts: 0
- Whole-disc diff limited to declared target LBAs: PASS
- MODE1/2352 EDC/ECC: PASS
- Historical integrated re-extraction: 19/19 PASS
- Estimated bytes: 0

## Assets

| Asset | Size | SHA-256 |
|---|---:|---|
| SYS03 | 82025 | f8e3c624a1d823f53dbf32e61a8c2ef930f46b829878ba52046aa9e973647603 |
| SYS02 | 82027 | c98d2a4a7cacf70b70f02a01b57f3d81743fce978f687c99fb1877ba0e8aaf86 |
| SYS05 | 82027 | badea278db907e4ba4f5b2074664f0426df15bd631f2b3b561cfae033c262ba7 |
| SYS08 | 82052 | 670efd5fc40a77eef11fc4bcc038ea1eb8eef5fac76288348db13fa023f9d9b3 |
| SYS17 | 82032 | 17a12d5c3df3e0fa2169c4433b22b73213b28556f720a4bb0e2a4a172ded012b |
| SYS07 | 82048 | 60b15eb70525e4ce0f7772fbb5a8abc7c02f6406361742a5b7470cb1ab196444 |

## Next

Recover and bind the B112 six-bank group to raise the exact baseline to 51/58.
