# Batch 236 — exact story structure closure and six-asset raw-sector integration gate

## Completed

Batch236 closes the byte-layout contract for SK0501, SK0502, SK0503, SKCM02, SKCM04 and SKCM05 without guessing any game bytes.

Historical Batch57/58/60 validation provides direct table/message/font addresses for SK0503/SK0502/SK0501. The retained translation ledgers and Batch62 validation provide exact file sizes, record counts, fixed allocation totals, font slot counts, unchanged pointer tables, unchanged control regions and exact compiled SHA-256 values. The following layout identities reproduce all three historical direct structures exactly:

- `font_start = file_size - font_slots * 128`
- `message_start = font_start - allocated_tokens * 2`
- `table_start = message_start - (4 + record_count * 4)`

Because the formulas reproduce all three independent historical direct anchors byte-for-byte, they are promoted as a deterministic structural contract and applied to the three Batch62 SKCM assets.

## Exact structures

| Asset | table_start | message_start | font_start | records | tokens | font slots |
|---|---:|---:|---:|---:|---:|---:|
| SK0501.BIN | `0xD514` | `0xED74` | `0x205DC` | 1559 | 35892 | 892 |
| SK0502.BIN | `0x4380` | `0x4B9C` | `0x9910` | 518 | 9914 | 537 |
| SK0503.BIN | `0x3AD8` | `0x4100` | `0x84AC` | 393 | 8662 | 495 |
| SKCM02.BIN | `0x40E0` | `0x475C` | `0x9CF4` | 414 | 10956 | 699 |
| SKCM04.BIN | `0x191C` | `0x1B4C` | `0x3F3C` | 139 | 4600 | 586 |
| SKCM05.BIN | `0x1948` | `0x1B40` | `0x3D18` | 125 | 4332 | 592 |

## Ledger proof

The four retained ledgers were executed through the Batch236 verifier. All six record streams are contiguous from word offset zero to their exact allocation end. Record counts and allocation totals match the frozen contract, and every one of the 3,148 records has a historical source-record SHA-256 anchor.

- SK0501: 1559/1559 SHA anchors
- SK0502: 518/518
- SK0503: 393/393
- SKCM02: 414/414
- SKCM04: 139/139
- SKCM05: 125/125

Total: 3,148/3,148 exact record SHA anchors.

## Production tool

`tools/verify_cd1_story_structure_batch236.py` now supports the next physical stage in one strict chain:

1. verify the exact pristine Disc1 whole-file SHA-256;
2. verify each source asset SHA-256;
3. verify each historical fixed-allocation source record at the exact message address;
4. accept replacement bodies only when their full size and compiled SHA-256 match the historical targets;
5. reject any LBA collision;
6. verify original MODE1/2352 EDC/ECC before a write;
7. record the full original-sector SHA as the Expected Write value and re-read it immediately before writing;
8. replace only the asset user-data bytes and regenerate Mode1 EDC, ECC-P and ECC-Q;
9. compare the complete source/output discs and reject any unregistered changed LBA;
10. re-extract all six assets from the output Disc and require their historical compiled SHA-256 values.

No game, font, movie or full Disc bytes are committed by Batch236.

## Runtime status

The structure/ledger contract self-test is PASS. A physical six-asset Disc candidate was not generated in this runtime because the exact pristine Disc1 raw BIN and the six historical compiled replacement bodies are not currently mounted as byte files. This does not weaken the structure closure: those bodies remain gated by their previously established full SHA-256 values.
