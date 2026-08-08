# Batch 237 — six-story full relative-address census and verifier hardening

Batch237 continues the Disc1 story integration line by turning the retained Batch57/58/60/62 translation ledgers into one exact structural census for SK0501, SK0502, SK0503, SKCM02, SKCM04 and SKCM05.

## Corrected execution defect

The first Batch236 verifier assumed that Batch62 exposed a top-level `records` array. The actual retained Batch62 ledger stores records under `files[SKCMxx.BIN].records`. That would have silently prevented SKCM02/04/05 from participating in the six-file ledger gate. `tools/verify_cd1_story_structure_batch236.py` is now corrected to read the nested structure first and use a top-level array only as a compatibility fallback. The verifier now also requires a 64-hex source-record SHA-256 anchor for every declared record and rejects incomplete six-ledger input sets.

## Exact census executed

The four retained ledgers were materialized and executed through the new census logic. No game bytes were inferred. All six record streams start at historical `source_word_offset=0` and continue without one allocation gap through the final fixed allocation.

| Asset | Records | 16-bit words | Bytes | Font slots | Used | Preserved |
|---|---:|---:|---:|---:|---:|---:|
| SK0501.BIN | 1,559 | 35,892 | 71,784 | 892 | 712 | 15 |
| SK0502.BIN | 518 | 9,914 | 19,828 | 537 | 509 | 15 |
| SK0503.BIN | 393 | 8,662 | 17,324 | 495 | 475 | 15 |
| SKCM02.BIN | 414 | 10,956 | 21,912 | 699 | 520 | 15 |
| SKCM04.BIN | 139 | 4,600 | 9,200 | 586 | 409 | 15 |
| SKCM05.BIN | 125 | 4,332 | 8,664 | 592 | 412 | 15 |
| **Total** | **3,148** | **74,356** | **148,712** | — | — | — |

All 3,148 records contain historical source-record SHA-256 anchors. Therefore the future absolute-address promotion gate can require every single fixed record allocation to match the pristine source bytes, not just a sample.

## Control census

The three SK050x streams retain their tokenized control vocabulary directly in `source_tokens_hex`. Census counts are: SK0501 FFFD=15 / FFFE=1,937 / FFFF=1,559; SK0502 FFFD=15 / FFFE=505 / FFFF=518; SK0503 FFFD=16 / FFFE=481 / FFFF=393.

The Batch62 SKCM streams preserve complex control pairs separately. Each SKCM file has 15 FFFC control records and 15 FFFA pairs plus one FFFB branch/continuation control. These controls stay outside any inferred text rewrite and remain governed by the historical record SHA and compiled target SHA.

## Relative-address production asset

`tools/build_story_structure_census_batch237.py` generates one row for every record with:

- asset name and record index;
- exact historical 16-bit `source_word_offset`;
- exact byte offset relative to the message-stream base;
- fixed token capacity and byte allocation;
- exact source-record SHA-256;
- record class and source confidence class;
- preserved control-code classes;
- unresolved source-glyph reference count.

The generated 3,148-row CSV has deterministic SHA-256 `262a12d4558a19c9a7e281d62fba95ca79bbb929a5b6abeea381211e9e063c7a` when produced from the retained four ledgers used in this batch. The repository stores the generator and the frozen census manifest rather than copyrighted dialogue bodies.

## Address promotion rule

Batch237 deliberately separates relative address proof from absolute address proof. A record's exact relative byte address is `source_word_offset * 2`. Absolute file/LBA/raw-sector coordinates are accepted only after the source asset body matches its frozen full SHA-256 and the selected message base makes all records in that asset match their historical source-record SHA-256 values. After that:

`file_offset = message_base + relative_byte_offset`

`iso_lba = asset_lba + file_offset // 2048`

`raw_disc_byte = iso_lba * 2352 + 16 + file_offset % 2048`

No guessed message base, glyph address or payload byte is promoted.

## Next physical gate

The tooling is now ready to consume a pristine Disc1 raw BIN or exact extracted six source assets and prove absolute table/message/font addresses against the record hashes. Once historical compiled replacement bodies are recovered, the existing strict chain remains: source SHA -> record-address proof -> replacement SHA -> Expected Write -> LBA collision check -> MODE1 EDC/ECC -> changed-sector accounting -> whole-asset re-extraction SHA.
