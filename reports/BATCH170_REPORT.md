# Batch 170 — PBOOK three-asset exact recovery gate

## Status

`PASS_PBOOK_3_EXACT_RECOVERY_CONTRACT_CREATED`

## Completed

The three PBOOK assets missing from the Batch169 55-asset package are now registered as an executable exact recovery set:

| Asset | LBA | Size | Source SHA-256 | Replacement SHA-256 | Changed sectors |
|---|---:|---:|---|---|---:|
| PBOOK_BT.CG | 15609 | 87,712 | `43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64` | `4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe` | 12 |
| PBOOK_EC.CG | 15652 | 87,456 | `3118ecdf03d7225f9666298b7c93b357c276bbdc27ce0b7020baca12003db3bc` | `378d92a4daf3db00d7c172ae8d233fad1fe3e1452cb979e9bd8b5610220152f5` | 5 |
| PBOOK_RC.CG | 15695 | 58,208 | `56f8607a5c3ab6c5ad79b1b3de2910822f3880fa7f2e3938b273a1dfa27bc201` | `c5bc0866ea5581f64bccb0a9da1c6baf53c77601fa247469441e49d0eaae4907` | 12 |

Total PBOOK changed raw sectors: **29**.

## Historical verification basis

Batch110 verified the PBOOK trio together with SYS26 and STNSYS00:

- 87 unique changed raw sectors across five assets;
- zero LBA conflicts;
- zero unrelated changed sectors;
- MODE1/2352 EDC/ECC PASS;
- re-extraction 5/5 PASS.

PBOOK_BT is the independent Batch110 reconstruction. It is not represented as byte-identical to the missing historical Batch82/83 file.

## New executable components

- `manifests/PBOOK_3_EXACT_TARGETS.json`
- `START_B170_RECOVER_PBOOK_3_EXACT.cmd`
- `.github/workflows/batch170-pbook-static.yml`

The launcher scans loose files, ZIP archives and retained full Disc checkpoints. A payload is accepted only when its complete size and replacement SHA-256 match. Application additionally requires the pristine Disc SHA, per-asset source SHA Expected Write, MODE1/2352 EDC/ECC regeneration, changed-sector accounting and exact re-extraction.

## Static closure state

- Batch137 exact battle banks: 55/55
- Exact PBOOK recovery contract: 3/3
- Combined deterministic static target: **58/58**
- Physical combined 58-asset candidate: requires the exact B137 package, all three exact PBOOK replacement payloads and the pristine Disc 1 BIN to be present in one runtime scan root.
