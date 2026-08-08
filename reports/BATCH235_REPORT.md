# Batch 235 — Disc1 story address / glyph atlas foundation

Batch235 expands the current CD1 story work from translation-ledger metadata into an exact byte-address recovery layer for six large story/auxiliary binaries: SK0501, SK0502, SK0503, SKCM02, SKCM04 and SKCM05.

The retained ledgers cover 3,148 records and 74,356 allocated 16-bit tokens. Per-file source-word offsets are contiguous with no ledger gaps across these six record streams. The address builder does not assume a message base address. It scans fixed-allocation record byte windows against the historical `source_record_sha256`, derives candidate message bases, and accepts a base only when every available record hash verifies at that one base. This is especially important for SKCM02/04/05 because their Batch62 ledger retains record SHA, offsets and capacities but does not retain full `source_tokens_hex` for each record.

Once a message base is proven, every record receives: exact file byte start/end, ISO LBA, MODE1/2352 user-data offset, raw-sector offset and absolute raw-disc byte address. No guessed pointer or inferred byte is emitted.

Font/glyph location is handled separately. The six ledgers prove 16x16, 4bpp high-nibble-first glyph geometry and per-file slot counts. Batch235 can ingest the retained BATCH108 128-byte glyph SHA oracle and scan all 128 alignment phases. A font base is promoted only when at least eight independent glyph hashes vote for the same `font_base = glyph_offset - slot*128`, the strongest vote is unique, and the complete declared slot span fits inside the asset. Otherwise the font address remains UNPROVEN instead of being guessed.

Static ledger census used by the contract:

- SK0501.BIN: 1,559 records, 35,892 tokens / 71,784 bytes, 892 font slots, 712 used, LBA 45704.
- SK0502.BIN: 518 records, 9,914 tokens / 19,828 bytes, 537 font slots, 509 used, LBA 45825.
- SK0503.BIN: 393 records, 8,662 tokens / 17,324 bytes, 495 font slots, 475 used, LBA 45878.
- SKCM02.BIN: 414 records, 10,956 tokens / 21,912 bytes, 699 font slots, 520 used, LBA 46030.
- SKCM04.BIN: 139 records, 4,600 tokens / 9,200 bytes, 586 font slots, 409 used, LBA 46094.
- SKCM05.BIN: 125 records, 4,332 tokens / 8,664 bytes, 592 font slots, 412 used, LBA 46139.

The address-locator algorithm was subjected to a synthetic fixed-allocation test: it recovered an injected message base exactly, then rejected the same stream after one byte was corrupted. The tool is therefore ready to run as soon as exact pristine source asset bodies are materialized from the verified Disc1 image or historical raw-disc candidates.

Safety remains unchanged: pristine source SHA-256 first, record SHA address proof, no speculative offsets, no game/font binaries committed, Expected Write before writes, MODE1 EDC/ECC after writes, and whole-asset re-extraction SHA before candidate promotion.
