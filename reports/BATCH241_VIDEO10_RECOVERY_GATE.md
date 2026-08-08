# Batch241 — remaining Video10 exact recovery gate

Status: **PASS TOOLING / NO GAME-BYTE PROMOTION**

Batch240 remains the only physical Disc parent: `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83`.

## Closed in this batch

The remaining ten historical movie candidates are now represented by a non-speculative recovery gate.

- B65 `ST2B65.zip` SHA-256 `37a0a3eb4e2ad4e9a351cfb0fdf863a6d9e5371b0942f902a0e7eef451ca5a29` -> `SK2MV_04.CAK`
- B66 `ST2B66.zip` SHA-256 `bbb918b66ec006400a622af961a184d8c5500b747f2eb15979ce67aa79aeeb0f` -> `SK2MV_05.CAK`
- B67 `ST2B67.zip` SHA-256 `8fc6dfca6db7b201d4d4dd898e31ddc0d9e3a2a770cc68a528cf653fb7213e67` -> `SK2MV_06.CAK`
- B64 exact standalone candidate: `SK2MV_30.CAK` SHA-256 `fab3dd471e909958774170770a9191683d16e670edfed0434167c1ea7e8a988a`
- B63 exact standalone candidates: `SK2MV_43.CAK` .. `SK2MV_48.CAK`, all seven? No: six title-card assets, each with fixed replacement SHA in the gate manifest.

`tools/recover_batch241_video10.py` refuses package/member ambiguity and never infers a payload. For B65/B66/B67 it first validates the whole ZIP SHA, then accepts exactly one member with the expected basename and exact asset size. For B63/B64 it requires the fixed candidate SHA-256.

## Safety boundary

Recovery success does **not** authorize a Disc write. The consolidated manifest emitted by the recovery tool has `promotion_allowed: false`. A later physical integration must still prove:

1. pristine source asset SHA;
2. Batch240-parent footprint overlap = 0;
3. raw-sector Expected Write;
4. all actual writes inside approved footprint;
5. EDC/ECC for every changed MODE1 sector;
6. changed-sector accounting;
7. exact whole-asset re-extraction;
8. exact final Disc SHA recorded after the run.

No copyrighted CAK, full Disc, or inferred binary bytes are committed.
