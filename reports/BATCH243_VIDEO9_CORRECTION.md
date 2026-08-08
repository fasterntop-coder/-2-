# Batch243 — correct Batch241/242 remaining-movie scope from Video10 to Video9

## Finding

Batch240 already physically integrated the exact B64 `SK2MV_30.CAK` replacement at LBA 134468. Batch240's final Disc SHA-256 is `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83` and its 94-asset union explicitly includes `SK2MV_30.CAK`.

The first Batch241 recovery gate incorrectly listed `SK2MV_30.CAK` again among the remaining movie payloads. The Batch242 integrator also requires every new target footprint to be byte-identical between pristine Disc and Batch240 parent before a write. Therefore the stale Video10 plan is internally impossible: the safety gate would reject the already-modified SK2MV_30 footprint, exactly as designed.

## Correction

The remaining physical movie scope is **9 assets**, not 10:

- trusted legacy packages: `SK2MV_04.CAK`, `SK2MV_05.CAK`, `SK2MV_06.CAK`
- exact standalone Batch63 candidates: `SK2MV_43.CAK` through `SK2MV_48.CAK`

`SK2MV_30.CAK` is excluded because it is already present in the authoritative Batch240 parent with replacement SHA-256 `fab3dd471e909958774170770a9191683d16e670edfed0434167c1ea7e8a988a`.

## Safety policy retained

No guessed payload bytes are introduced. Physical promotion still requires:

1. exact trusted-package SHA-256 or exact standalone candidate SHA-256,
2. pristine source-asset SHA-256,
3. authoritative Batch240 parent SHA-256,
4. zero overlap with pre-existing Batch240 changes,
5. raw-sector Expected Write,
6. MODE1/2352 EDC/ECC regeneration and verification for every changed sector,
7. changed-sector accounting with no writes outside approved footprints,
8. whole-asset re-extraction matching all replacement SHA-256 values.

## Repository changes

- corrected `manifests/CD1_BATCH241_VIDEO10_RECOVERY_GATE.json` to the Video9 v2 contract,
- corrected `tools/recover_batch241_video10.py` to recover exactly 9 remaining assets and reject `SK2MV_30.CAK`,
- corrected the Batch242 preflight cardinality to 3 trusted ZIPs + 6 direct candidates,
- added `tools/integrate_batch241_video9_batch242.py`, which reuses the existing audited Expected Write / EDC-ECC implementation while replacing only the stale Video10 manifest/cardinality contract.

## Current physical block

Promotion remains blocked until the exact 9 payload sources are available:

- `ST2B65.zip` SHA-256 `37a0a3eb4e2ad4e9a351cfb0fdf863a6d9e5371b0942f902a0e7eef451ca5a29`
- `ST2B66.zip` SHA-256 `bbb918b66ec006400a622af961a184d8c5500b747f2eb15979ce67aa79aeeb0f`
- `ST2B67.zip` SHA-256 `8fc6dfca6db7b201d4d4dd898e31ddc0d9e3a2a770cc68a528cf653fb7213e67`
- exact `SK2MV_43.CAK` through `SK2MV_48.CAK` candidates with the replacement SHA-256 values frozen in the v2 gate.

The SHA sidecars and historical QA/manifests alone are not substitutes for these payload bytes.
