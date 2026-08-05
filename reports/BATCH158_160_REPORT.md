# ST2 Disc 1 — Batch 158–160 direct exact recovery promotion

## Result

The direct battle/static recovery contract now composes the verified cumulative lineage without parsing historical workbooks at execution time:

- Batch 158: B116 cumulative 42 exact assets
- Batch 159: B117 cumulative 56 exact assets
- Batch 160: B118 cumulative 58 exact assets

## Exact deltas

### Batch 116

Nine banks are added to the trusted B115 33-asset base:

`SYS20`, `SYS47`, `STNSYS02`, `SYS21`, `STNSYS03`, `SYS23`, `SYS24`, `SYS22`, `SYS25`

Historical cumulative gates:

- assets: 42
- changed raw sectors: 1,162
- LBA conflicts: 0
- changes outside declared sectors: 0
- MODE1/2352 EDC/ECC: PASS
- re-extraction: 42/42 PASS
- verification BIN SHA-256: `d318c3a5a0291483da6ee1626341f561ac26c34009be502dbe07222abd5b8088`

### Batch 117

Fourteen banks are added:

`SYS06`, `SYS28`, `SYS30`, `SYS32`, `SYS35`, `SYS38`, `SYS39`, `SYS40`, `SYS41`, `SYS42`, `SYS43`, `SYS44`, `SYS48`, `SYS50`

Historical cumulative gates:

- assets: 56
- changed raw sectors: 1,568
- LBA conflicts: 0
- changes outside declared sectors: 0
- MODE1/2352 EDC/ECC: PASS
- re-extraction: 56/56 PASS
- verification BIN SHA-256: `83481538455dc236100629f60b2e9349d10ccef8e28141591464db2ff21bfd07`

### Batch 118

The final two banks are added:

`SYSTEM`, `SYS14`

Historical cumulative gates:

- assets: 58
- battle banks: 55/55
- battle records: 12,595/12,595
- changed raw sectors: 1,626
- LBA conflicts: 0
- changes outside declared sectors: 0
- MODE1/2352 EDC/ECC: PASS
- re-extraction: 58/58 PASS
- verification BIN SHA-256: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

## New executable path

`START_B160_RECOVER_BATCH118_58_ASSETS.cmd` performs these steps:

1. compose and validate the B116 42-asset manifest;
2. compose and validate the B117 56-asset manifest;
3. compose and validate the B118 58-asset manifest;
4. scan loose files, ZIP members and MODE1/2352 checkpoint BINs;
5. emit only complete assets whose size and whole-file SHA-256 exactly match.

## Safety

- no binary game assets are committed;
- no hash inversion, approximate payload or guessed byte is accepted;
- base-batch discontinuity, cumulative-count mismatch, duplicate asset name or duplicate starting LBA aborts composition;
- the existing source Disc SHA, Expected Write, EDC/ECC and re-extraction gates remain authoritative for final integration.

## Runtime dependency

A real recovered 58-asset vault still requires retained loose translated assets or checkpoint BIN/ZIP bytes containing those exact targets. The repository now has one deterministic entry point for all 58 historical targets.
