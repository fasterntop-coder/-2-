# Batch 207 — Legacy cumulative chain replay and exact regression repair

## Status

`PASS_EXACT_REPLAY_3_OF_3_AND_LBA208689_REGRESSION_ISOLATED_REPAIR_READY`

## Actual runtime replay

The exact pristine Disc 1 was extracted from File Library and used independently for all three legacy cumulative packages.

- Source Disc size: `659,293,824`
- Source Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`

Reproduced outputs:

| Package | Changed sectors | Reproduced output SHA-256 |
|---|---:|---|
| Batch55 | 40,148 | `6dc33248b5c33ca979c05bc10fd25a1072313b968fa7f549bd9a5d7e381787c0` |
| Batch59 | 55,603 | `373878d7aaed99ecd143aadcd92c11203d94689b256eb105b4d49e311afe0774` |
| Batch60 | 59,051 | `7f57743b947704963290e2e108485262c940690c4a3c8d60800a7ae3338f397d` |

All three outputs matched their package manifests exactly.

## Exact cumulative-chain finding

- Batch59 adds 15,456 sectors relative to Batch55.
- Batch59 drops exactly one prior changed sector: **LBA 208689**.
- Batch60 adds another 3,448 sectors and preserves the Batch59 sector set, so it inherits the same omission.
- Batch55 LBA 208689 sector SHA-256: `97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0`
- Pristine LBA 208689 sector SHA-256: `3da035f48eb2cdd51b4248b5881b1fe2f30f0779234ce553eca7387286df0246`

This is a byte-proven cumulative regression, not an inferred translation issue.

## Exact repair

Restoring the exact Batch55 sector into the exact Batch60 replay produces:

- Repaired whole-BIN SHA-256: `845a6ec09fcf846bbae9a996d63966692908c9fc85d6a2e5a518c9b06f4cbe21`
- Changed sectors relative to pristine: 59,052
- Restored raw sector passes MODE1/2352 EDC, ECC-P and ECC-Q validation.

## Added tooling

- `tools/audit_legacy_cumulative_patch_chain.py`
- `tools/repair_batch60_dropped_lba208689.py`

Both tools require exact hash-addressed payloads. No estimated bytes are generated. Full verification BINs were deleted after hashing and are not committed.
