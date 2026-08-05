# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- SYS23: exact recovery complete
- B116: 9/9 banks complete
- Current exact local scope: 39/58
- Historical static certificate: 58/58

## Current batch

### Batch 144 — PASS

The retained historical B110/B118 apply scripts can now be converted into normalized exact-sector manifests without executing legacy code.

New component:

- `tools/extract_apply_manifest.py`
- `reports/BATCH144_REPORT.md`

The parser uses Python AST plus `literal_eval` only and extracts historical `SECTORS`, `SEC` or `M` dictionaries into `st2-exact-sector-manifest-v1`.

## B118 recovered metadata path

The File Library copy of `batch118_apply_to_original_bin.py` contains the complete 1,626-sector metadata dictionary together with:

- Source BIN size: 659,293,824 bytes
- Source BIN SHA: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Target BIN SHA: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`
- Per-sector Expected Write SHA-256
- Per-sector patched payload SHA-256
- Asset attribution and payload filenames

The new parser validates and normalizes this data without trusting or running the historical script.

## Exact recovery chain

1. `tools/extract_apply_manifest.py`
2. `tools/recover_exact_patch_from_manifest.py`
3. `START_B118_EXACT_RECOVERY.cmd`
4. `tools/recover_pbook_bt_b110.py`
5. `START_B142_RECOVER_PBOOK_BT.cmd`

## Safety gates

- Legacy apply scripts are never executed.
- Duplicate LBAs and malformed or missing SHA gates fail closed.
- Original sectors require Expected Write SHA-256 matches.
- Patched sector bodies require exact 2,352-byte SHA-256 matches.
- Full output BIN must match the historical target SHA.
- Failed output images are removed.

## CI

GitHub Actions run 8: SUCCESS.

All compilation, parser self-test, PBOOK recovery, patched-sector harvesting, Expected Write application, sparse package generation and full-output roundtrip tests passed.

## Active blocker

The complete B118 metadata is recoverable, but the actual 2,352-byte patched-sector payload bodies or a retained exact B118 target BIN are not present in File Library. SHA-256 values cannot be reversed into missing sector bytes.

## Next

Continue scanning retained ZIP/BIN material for any later-lineage image or PATCH_SECTORS directory. On a match, the normalized manifest and exact recovery engine can immediately create the 58-asset sparse patch and SHA-gated BIN/CUE candidate.
