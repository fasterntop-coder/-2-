# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Exact battle-bank physical recovery: 55/55
- Exact PBOOK physical recovery: 3/3
- Exact battle/static physical recovery: 58/58
- Exact large-story physical recovery/integration: 6/6
- Current exact physical union: 64 assets
- Exact story/movie production scope: 42 assets
- Authoritative workflow: one `main` lineage only; parallel workflows forbidden

## Current batch

### Batch 239 — PASS STATIC58 + STORY6 PHYSICAL UNION 64/64

The six previously blocked story/auxiliary binaries SK0501, SK0502, SK0503, SKCM02, SKCM04 and SKCM05 have now been recovered as real historical byte bodies from retained File Library packages and physically integrated with the exact 58-asset battle/static baseline.

## Exact pristine source

- archive: `015 Sakura Taisen 2 Disc 1 of 3 (J) (2)(1).zip`
- archive size: `458,507,639`
- archive SHA-256: `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- BIN size: `659,293,824`
- BIN SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`

## Batch238 absolute address proof

The pristine source directly proved all six file structures:

- source assets: `6/6` exact full SHA
- source MODE1 sectors: `376/376` EDC/ECC PASS
- records: `3,148/3,148` historical source SHA PASS
- BE32 pointer entries: `3,148/3,148` equal historical word offsets
- source glyph slots physically addressed and hashed: `3,801`
- absolute record address atlas SHA-256: `6ac8310a19ca4a1ce28647d358fda8c76e5d710d29f764650ffd53c887484ad2`
- glyph-slot physical address atlas SHA-256: `8953017fdae68c2b80c8ae8adca26b416e91bd13262472e9af074ae46a0e0795`
- guessed addresses/bytes: `0`

The final record in each of the six files has zero padding after its actual `FFFF` terminator. Historical record SHA covers the unique FFFF-terminated prefix, not that final zero pad. This has been incorporated into the new proof tool.

## Recovered historical story payload packages

- `ST2R41_B57_SK0503_BIN.zip` SHA-256 `6d8a4b1f8689b324ff1effe26188ec4f9447a225b06a72a21d67159e6159276c`
- `ST2R41_B58_SK0502_BIN.zip` SHA-256 `651dc3e6ed3f968d99bc9cce0c99f00c634dcc5926230a8278caa85846bc2575`
- `ST2R41_B60_SK0501_BIN.zip` SHA-256 `4fbae3d8bdc08a1d68064f6ca07c7d467a2ff93612fa3f91c06c7116c91bb6f9`
- `ST2R41_B62_SKCM_BIN.zip` SHA-256 `9500e58d4cdd8f99cd9f7a4179bf1799876c6248f56593bd721386ac8c636216`

All six contained BIN bodies match their historical compiled SHA-256 values exactly.

## Physical integration result

Story-only from pristine:

- approved file footprint: `376` sectors
- actual changed sectors: `275`
- outside-footprint changes: `0`
- re-extraction: `6/6 PASS`
- MODE1 EDC/ECC failures: `0`
- story-only Disc SHA-256: `d8f4513cdd4e43d6020fb8bf2403c458ced30112002019c934f9c09d7e503a10`

Static58 parent was independently rebuilt again from the retained B118 raw-sector package and reproduced exact SHA-256:

`75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

Final static58 + story6 union:

- physical assets: `64/64`
- static re-extraction: `58/58 PASS`
- story re-extraction: `6/6 PASS`
- static changed sectors: `1,626`
- story changed sectors: `275`
- total changed sectors from pristine: `1,901`
- LBA conflicts: `0`
- unregistered changed sectors: `0`
- MODE1 EDC/ECC: `1,901/1,901 PASS`
- final Disc SHA-256: `daa1052fabd4142feaf42f14bdb5deefdf486cea8f0db8c939fc18ce6f822a56`

The full Disc image is local verification output only and is not committed or distributed.

## Corrected write-gate semantics

The earlier assumption that every raw sector touched by an asset extent must change is retired. Headers, pointer tables, preserved control data and tail space may remain byte-identical. The authoritative rule is now:

- candidate full SHA must match;
- source Expected Write must match before write;
- actual changed sectors must be a subset of the declared asset footprint;
- no change outside approved footprints;
- all resulting changed sectors must pass MODE1 EDC/ECC;
- whole assets must re-extract to expected SHA.

## Current production components

- `tools/prove_cd1_story_absolute_addresses_batch238.py`
- `manifests/CD1_STORY_ABSOLUTE_ADDRESS_PROOF_BATCH238.json`
- `tools/integrate_static58_story6_batch239.py`
- `manifests/CD1_STATIC58_STORY6_UNION_BATCH239.json`
- `reports/BATCH239_REPORT.md`

## Mandatory safety policy

- no estimated or inferred payload bytes;
- exact pristine Disc SHA-256 required before raw-disc work;
- exact source asset, pointer and record SHA proof required for promoted story addresses;
- exact source-sector Expected Write required before every write;
- exact replacement payload SHA-256 required;
- MODE1 EDC, ECC-P and ECC-Q required after writes;
- changed-sector accounting required;
- exact whole-asset re-extraction required;
- no copyrighted game, font, asset, movie or full Disc bytes committed to GitHub.

## Next production priority

Use Batch239 as the new physical Disc1 parent. Recover the next already-promoted story/movie payload packages from File Library and union them in large groups, not one-file micro-batches. Every new union must preserve the exact 64-asset baseline and pass Expected Write -> overlap/collision -> MODE1 EDC/ECC -> changed-sector accounting -> whole-asset re-extraction before promotion.
