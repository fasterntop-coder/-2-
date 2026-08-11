# Batch 309 — B308 + exact R39 UI/runtime/title 11-asset physical union

Batch309 keeps the Batch308 core physical/static inventory at **223/223 PASS** and physically adds 11 exact R39 assets that were still pristine in Batch308.

## Added exact assets

- battle command UI: `CMD_WIN.CG`
- battle visual UI: `PBOOK_FL.CG`, `PB_EYE.CG`
- battle font: `BTSFONT.BIN`
- runtime low-font banks: `M00LOW.BIN`, `M01LOW.BIN`, `M26LOW.BIN`, `M27LOW.BIN`
- title assets: `TITLE.BIN`, `TTL2CGB.BIN`, `TTL2CGB1.BIN`

The exact donor is the reconstructed R39 Disc SHA-256 `57335616e481102fe2ef7ab080871df479211f388eff796d5c6bca7a28958025`. Every target was promoted only where the Batch308 whole asset exactly matched pristine; 49 R39 paths holding newer third-variant content in Batch308 were deliberately left untouched.

## Physical result

- parent Batch308 SHA-256: `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f`
- Batch309 SHA-256: `8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01`
- new assets: **11/11 re-extraction PASS**
- new footprint: 1,174 sectors
- new changed sectors: 144
- Expected Write records: 1,174
- cumulative changed sectors vs pristine: 90,272
- all final changed-sector MODE1 EDC/ECC: **90,272/90,272 PASS**
- LBA collisions: 0
- outside-footprint changes: 0
- third variants accepted: 0
- guessed payload bytes: 0

`CMD_WIN.CG` in Batch309 has SHA-256 `20a4947ce98752681efecffe9a6022dfb324bc9433ece5ce8da6d567f605ee09`, exactly matching the previously validated Korean battle-command texture used for the real UI preview.

Hardware/playback validation remains pending, so Batch309 is an exact physical/static candidate rather than a hardware-certified public release.
