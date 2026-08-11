# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- **Current physical/static inventory: 223/223 = 100.0%**
- Story: **141/141**
- Battle/static: **58/58**
- Movie static inventory: **24/24**
- Authoritative workflow: one `main` lineage only; guessed bytes forbidden

## Current authoritative candidate

### Batch 308 — PASS REAL PHYSICAL/STATIC 223/223

Batch308 is an actual rebuilt MODE1/2352 Disc 1 candidate, not logical accounting alone.

- pristine Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Batch308 Disc SHA-256: `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f`
- Disc size: `659,293,824`
- physical/static assets accounted: `223/223`
- final whole-asset re-extraction: `223/223 PASS`
- changed sectors vs pristine: `90,128`
- changed-sector MODE1 EDC/ECC: `90,128/90,128 PASS`
- guessed payload bytes: `0`
- third variants accepted: `0`
- changes outside approved footprints: `0`

The physical chain used to reach Batch308 is:

- Batch240: 94 assets, SHA `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83`
- Batch305 physical union: 142 assets, SHA `93b3b08ff5e27f03e056ec3577068a2ae2b91cc3d961fc5628ad79a479a871b1`
- Batch306 physical union: 172 assets, SHA `b99a4aebdec0412accf843366fa70b406ccaad1be769fe33b95d81ab36ad4302`
- Batch307 80% gate: 179 assets, SHA `137a278985d1659cbf21d106683b50dba092a4d31f198f8dd7cd5573b311909c`
- Batch308 100% physical/static candidate: 223 assets, SHA `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f`

Batch308 adds 33 exact replacement assets and 11 exact identity controls over Batch307. The final 223/223 gate was rerun against the produced Batch308 BIN: all 223 expected whole assets were re-extracted from the final image and hashed, and all 90,128 sectors that differ from pristine passed MODE1 EDC/ECC verification.

## Hardware/release status

**Hardware validation is still pending.** Batch308 is therefore the authoritative **100% physical/static candidate**, not yet the final hardware-certified public release. Re-encoded subtitle/title-card movies must still be playback-tested for timing, visual presentation and stability, and any runtime regressions found in emulator/real hardware testing must be repaired without breaking the Batch308 safety gates.

## Current production components

- `manifests/CD1_BATCH308_REAL_PHYSICAL_STATIC_223_OF_223.json`
- `reports/BATCH308_REAL_PHYSICAL_STATIC_100_PERCENT.md`
- `tools/verify_batch308_real_physical_static_100.py`

## Mandatory safety policy

- no estimated/inferred payload bytes;
- exact source and candidate SHA-256;
- raw-sector Expected Write before writes;
- actual changes only inside approved footprints;
- EDC/ECC on every changed output sector;
- changed-sector accounting;
- exact whole-asset re-extraction;
- identity controls must remain exact where required;
- no copyrighted game/font/movie/full-Disc bytes committed.

## Next production priority

Use Batch308 SHA `b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f` as the physical/static candidate for regression and playback validation. Prioritize movie timing/playback, battle/UI presentation, runtime crash checks and any remaining visual/wording defects. Any correction must retain Expected Write, exact changed-sector accounting, MODE1 EDC/ECC and whole-asset gates.
