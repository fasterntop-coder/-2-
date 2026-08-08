# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Exact battle-bank physical recovery: 55/55
- Exact PBOOK physical recovery: 3/3
- Exact battle/static physical recovery: 58/58
- Historical battle/static certificate: 58/58
- Exact story/movie production scope: 42 assets
- Authoritative workflow: one `main` lineage only; parallel workflows forbidden

## Current batch

### Batch 237 — PASS SIX-STORY RELATIVE ADDRESS CENSUS 3,148/3,148

The battle/static baseline remains physically closed at 58/58. Current production work is on the story/movie integration line.

Batch237 hardens the six large story/auxiliary assets SK0501, SK0502, SK0503, SKCM02, SKCM04 and SKCM05. The retained Batch57/58/60/62 ledgers were executed as one structural census. All 3,148 records have contiguous fixed allocations and all 3,148 carry historical source-record SHA-256 anchors. Total fixed message allocation is 74,356 16-bit words / 148,712 bytes.

A defect in the Batch236 verifier was corrected: Batch62 stores SKCM records under `files[name].records`, not a required top-level record array. The verifier now consumes the nested structure, requires every declared record SHA anchor, rejects incomplete six-ledger input sets, and rejects source assets when any exact record address/hash check fails.

## Real recovery baseline

- pristine Disc 1 archive: `015 Sakura Taisen 2 Disc 1 of 3 (J) (2)(1).zip`
  - size: `458,507,639`
  - SHA-256: `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- pristine BIN:
  - size: `659,293,824`
  - SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- exact battle/static verification BIN SHA-256: `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

## Batch237 story structure result

- story/auxiliary assets covered: `6`
- exact record allocations: `3,148/3,148`
- historical record SHA anchors: `3,148/3,148`
- allocated words: `74,356`
- allocated bytes: `148,712`
- allocation gaps: `0`
- guessed payload bytes: `0`
- deterministic relative-address CSV SHA-256: `262a12d4558a19c9a7e281d62fba95ca79bbb929a5b6abeea381211e9e063c7a`

## Current story replacement targets

- SK0501.BIN -> `6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743`
- SK0502.BIN -> `0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc`
- SK0503.BIN -> `c844f857de7260e0b2746d7702460709393d8b08821986129cc5e09de103e76b`
- SKCM02.BIN -> `0a2d0edf358b8fe6ab6edbc058e7e1263fc466706312bec43fd9994eb38419d9`
- SKCM04.BIN -> `c3e78d0b32b87d58d720c0fdd616fbc2fba232b306abe8c528d66a524664c4f8`
- SKCM05.BIN -> `cfd966f1cc1783f0da0f988aba92bd7591237cacb10c633da0063ce1f71c29f4`

## Batch237 components

- `tools/build_story_structure_census_batch237.py`
- `tools/verify_cd1_story_structure_batch236.py` (hardened loader/gates)
- `manifests/CD1_STORY_STRUCTURE_CENSUS_BATCH237.json`
- `manifests/CD1_STORY_EXACT_STRUCTURE_BATCH236.json`
- `reports/BATCH237_REPORT.md`

## Single-lineage rule

All future work must fetch the latest `main`, read `PROJECT_STATUS.md` and `manifests/SINGLE_LINEAGE_LOCK.json`, then perform exactly one next production task on this lineage. Parallel batches or independent chat-driven writes are forbidden.

## Mandatory safety policy

- no estimated or inferred payload bytes;
- exact pristine Disc SHA-256 required before raw-disc work;
- exact source asset and source-record SHA-256 required before absolute address promotion;
- exact source-sector Expected Write SHA-256 required before every write;
- exact replacement payload SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q required after writes;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no copyrighted game, font, asset, movie or full Disc bytes committed to GitHub.

## Next production priority

Recover or materialize exact source/replacement bodies for the six story targets, promote all 3,148 relative record coordinates to exact file/LBA/raw-sector addresses, then integrate those six assets into the verified 58-asset battle/static baseline under Expected Write -> LBA collision -> EDC/ECC -> changed-sector accounting -> re-extraction gates. After that, continue the remaining promoted story/movie assets toward the single CD1 100% candidate.
