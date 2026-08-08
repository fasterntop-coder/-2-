# Batch 239 — physical union of the verified 58-asset static baseline and six large story assets

Batch239 converts the previously blocked six-story line into a real Disc1 integration result. This batch used retained byte bodies from File Library, not reconstructed or inferred payloads.

## Recovered physical inputs

The exact pristine archive was recovered from File Library and verified:

- `015 Sakura Taisen 2 Disc 1 of 3 (J) (2)(1).zip`
- size `458,507,639`
- SHA-256 `d848e44f6d959d4c80f180196eee64eb29c0fa2be77365716de91899997840a4`
- contained BIN size `659,293,824`
- contained BIN SHA-256 `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`

The historical compiled replacement bodies were also recovered from their original retained packages:

- B57 `ST2R41_B57_SK0503_BIN.zip` -> SK0503.BIN
- B58 `ST2R41_B58_SK0502_BIN.zip` -> SK0502.BIN
- B60 `ST2R41_B60_SK0501_BIN.zip` -> SK0501.BIN
- B62 `ST2R41_B62_SKCM_BIN.zip` -> SKCM02.BIN, SKCM04.BIN, SKCM05.BIN

All six replacement bodies exactly match their frozen historical compiled SHA-256 values.

## Absolute story structure proof

Before any write, Batch238-style proof was executed directly against the pristine Disc. All six source assets re-extracted to their exact source SHA. The 376 source sectors covering the six assets passed MODE1 EDC/ECC.

The six story files contain 3,148 records. Their big-endian tables were parsed directly from source bytes. For every file, the first table word is `record_count + 1` and every following BE32 pointer equals the retained historical `source_word_offset` for that record. All 3,148 pointers passed.

All 3,148 historical `source_record_sha256` anchors were then verified at the proven message addresses. The final allocation in each file has zero padding after its real FFFF terminator; therefore the last record SHA covers the unique FFFF-terminated prefix rather than the entire message-to-font allocation. Exact final zero pads are 4, 4, 2, 4, 2 and 4 bytes for SK0501, SK0502, SK0503, SKCM02, SKCM04 and SKCM05 respectively.

The resulting absolute record-address atlas contains 3,148 rows and SHA-256 `6ac8310a19ca4a1ce28647d358fda8c76e5d710d29f764650ffd53c887484ad2`. A second atlas maps all 3,801 source font slots to file/LBA/raw-disc addresses and exact 128-byte glyph SHA values; its SHA-256 is `8953017fdae68c2b80c8ae8adca26b416e91bd13262472e9af074ae46a0e0795`.

## Six-story physical integration

The six candidates cover 376 raw sectors, but only 275 sectors actually differ. This exposed and corrected an overly strict earlier gate assumption. A candidate's entire file footprint does not have to change: headers, pointer tables, preserved controls and unused tails can remain exactly equal to the source. The safe requirement is that all actual changed sectors are contained inside approved candidate footprints and that no sector outside those footprints changes.

Story-only physical Disc result from pristine:

- candidates: 6/6 exact SHA PASS
- source footprint: 376 sectors
- actual changed sectors: 275
- unregistered changed sectors: 0
- MODE1 EDC/ECC failures: 0
- re-extraction: 6/6 PASS
- Disc SHA-256: `d8f4513cdd4e43d6020fb8bf2403c458ced30112002019c934f9c09d7e503a10`

Per-file actual changed ranges are:

- SK0501: 82 sectors, LBA 45733-45814
- SK0502: 43 sectors, LBA 45834-45876
- SK0503: 40 sectors, LBA 45886-45925
- SKCM02: 46 sectors, LBA 46038-46083
- SKCM04: 32 sectors, LBA 46097-46128
- SKCM05: 32 sectors, LBA 46142-46173

## Static58 + Story6 union

The original B118 physical package was independently recovered again and applied to the pristine Disc using its own 1,626 source-sector Expected Write hashes and exact sector payloads. The reconstructed parent Disc SHA is exactly the historical static baseline:

`75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`

The six story footprints are disjoint from all 58 static asset extents. The story candidates were then written over this verified parent. Every story footprint sector was first checked to still equal the pristine source sector before writing.

Final union result:

- static assets: 58/58 re-extraction PASS
- story assets: 6/6 re-extraction PASS
- total physical assets: 64/64 PASS
- static changed sectors: 1,626
- story changed sectors: 275
- union changed sectors from pristine: 1,901
- LBA collisions: 0
- unregistered changed sectors: 0
- changed-sector MODE1 EDC/ECC: 1,901/1,901 PASS
- final Disc SHA-256: `daa1052fabd4142feaf42f14bdb5deefdf486cea8f0db8c939fc18ce6f822a56`

The full Disc image remains local and is not committed or distributed.

## Production tooling

- `tools/prove_cd1_story_absolute_addresses_batch238.py`
- `manifests/CD1_STORY_ABSOLUTE_ADDRESS_PROOF_BATCH238.json`
- `tools/integrate_static58_story6_batch239.py`
- `manifests/CD1_STATIC58_STORY6_UNION_BATCH239.json`

The next production step is no longer recovery of these six files. They are physically integrated. The next line should recover and union the next already-promoted story/movie assets into the exact Batch239 parent while retaining the same Expected Write, collision, EDC/ECC, changed-sector and re-extraction gates.
