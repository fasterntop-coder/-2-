# Batch 229 — CD1 static 58/58 baseline promotion

## Result

`PASS_CD1_STATIC58_BATCH229`

The previous 51/58 exact static baseline is extended with the seven foundational assets already proven in the historical Batch118 full-disc integration:

- PBOOK_BT
- PBOOK_EC
- PBOOK_RC
- SYS00
- SYS01
- SYS26
- STNSYS00

This closes the tracked CD1 battle/static asset set at **58/58** and the battle-bank census at **55/55**.

## Evidence gate

Batch118 validation records:

- 12,595 / 12,595 battle-static records
- 1,626 changed raw sectors
- 0 LBA conflicts
- 0 non-target changed sectors
- MODE1/2352 EDC/ECC PASS
- 58/58 byte-exact re-extraction PASS
- verification BIN SHA-256 `75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20`
- CUE SHA-256 `e7c80b2f7235cfffc7ba729fea20a08e80b828a7f42cc08ec196a91ed8df2e20`

No estimated bytes are accepted by this promotion.

## Important scope

This is **static asset completion**, not overall Disc 1 completion. The official overall CD1 runtime implementation ledger remains 46.3% until story, movie, UI/graphics and static payloads are assembled into one validated Disc 1 candidate. PBOOK_BT remains an independently reconstructed candidate rather than a byte-identical recovery of the missing historical Batch82/83 binary, although its candidate SHA is fixed and it passed the Batch118 full-disc/re-extraction gate.

## Next

The next productive CD1 path is no longer battle-static reconstruction. Work should move to recovering/assembling the story + movie + UI payloads into the immutable-original master build and raising the official whole-disc implementation ledger without changing bytes from unverified inference.
