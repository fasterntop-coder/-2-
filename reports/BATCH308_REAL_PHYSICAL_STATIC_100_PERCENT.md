# Batch 308 — Disc 1 real physical/static 223/223 candidate

Batch308 closes the current Disc 1 logical inventory on an actual rebuilt MODE1/2352 image. No game image bytes are committed to GitHub; the full BIN remains a local verification artifact.

## Result

- status: `PASS_B308_FINAL_223_OF_223_WHOLE_ASSET_AND_ALL_CHANGED_SECTOR_GATE`
- pristine SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Batch307 parent SHA-256: `137a278985d1659cbf21d106683b50dba092a4d31f198f8dd7cd5573b311909c`
- Batch308 output SHA-256: `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f`
- physical/static inventory accounted: **223/223 = 100.0%**
- story: **141/141**
- battle/static: **58/58**
- movie inventory: **24/24**

Batch308 adds 44 previously unaccounted logical assets over the exact Batch307 candidate: 33 exact replacements and 11 byte-identical identity controls. The new replacement set consists of 15 early SAKURA1 story banks + EV01001 from the exact R39 donor, six R37/R39 speech movies, eight late story banks, and three retained B65-B67 subtitle movies. Identity controls are five story/control files and six no-dialogue movies that remain pristine by design.

## Physical verification

- Batch308 newly approved footprint: 66,561 sectors
- Batch308 newly changed sectors: 51,437
- final changed sectors vs pristine: **90,128**
- Expected Write records for the Batch308 footprint: 66,561
- new footprint collisions: 0
- changes outside the approved footprint: 0
- third variants accepted: 0
- guessed payload bytes: 0
- Batch308 new replacement whole-asset re-extraction: 33/33 PASS
- Batch308 identity whole-asset re-extraction: 11/11 PASS
- **final whole inventory re-extraction: 223/223 PASS**
- **final changed-sector MODE1 EDC/ECC: 90,128/90,128 PASS**

The final 223/223 gate was rerun from the produced Batch308 BIN, not inferred only from manifests. Expected candidate hashes were rebuilt from the exact B118/B239/B240/B305/B306/B307 trust chain plus the new Batch308 exact donors and payload packages, and every final whole asset was re-extracted from the output image and hashed.

## Important release status

This is a **100% physical/static candidate**, not yet a hardware-certified final release. Re-encoded subtitle/title-card movies still require emulator/real-hardware playback validation for timing, stability and visual presentation. This caveat does not reduce the static inventory accounting or the sector/hash gates above.
