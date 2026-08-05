# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 143 — PASS

The project now has an executable exact recovery path for the historical B117/B118 full integration, rather than analysis-only records.

New toolchain:

1. `tools/recover_exact_patch_from_manifest.py`
2. `START_B118_EXACT_RECOVERY.cmd`
3. `tools/recover_pbook_bt_b110.py`
4. `START_B142_RECOVER_PBOOK_BT.cmd`
5. `reports/BATCH142_REPORT.md`
6. `reports/BATCH143_REPORT.md`

## B118 target

- Battle banks: 55/55
- Battle records: 12,595/12,595
- Integrated assets: 58
- Changed raw sectors: 1,626
- Source BIN SHA: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Target BIN SHA: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

## Exact recovery behavior

- Parses the historical apply script with AST without executing it.
- Recovers sector payloads from loose files, ZIP members or an exact historical output BIN.
- Checks every original LBA with Expected Write SHA-256.
- Checks every 2,352-byte patched-sector SHA-256.
- Creates a sparse exact-sector patch ZIP.
- Creates a full BIN only from the exact pristine Disc 1 source.
- Requires the complete output BIN SHA gate before reporting success.
- Deletes failed output images.

## CI

GitHub Actions run 6: SUCCESS.

Compilation, manifest parsing, patched-sector harvesting, Expected Write application, sparse package creation and whole-output byte-exact roundtrip all passed.

## Active blocker

The exact B117/B118 patched-sector bytes or a retained exact historical B117/B118 full BIN are not present in File Library. The source Disc 1 and apply manifests are known, but SHA values alone cannot reconstruct the missing 2,352-byte sector bodies.

## Next

Continue searching retained archives and later-lineage images for the exact B118 sectors. When found, the current engine will immediately generate the 58-asset sparse patch and the SHA-gated BIN/CUE candidate.
