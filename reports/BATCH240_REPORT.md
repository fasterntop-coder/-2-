# Batch 240 — Batch239 + 27 story MES + 3 subtitle movies, physical 94-asset union

Batch240 advances the Disc1 physical lineage in one large production step. The retained B51, B52 and B64 payload packages were recovered from File Library and applied over the exact Batch239 parent rather than re-created from translation text.

## Recovered exact payload packages

- `ST2R41_B51_MES.zip`: 9 Episode-4 event MES assets, SHA-256 `a513b7d127112070ccecec9af11f42c6ed878611373b3e47616ed6f153cac8e3`
- `ST2R41_B52_MES.zip`: 18 Episode-5 event MES assets, SHA-256 `26952e76b5966166b669d386460c55845a5a936c96bc07a71b14679a995458fd`
- `ST2R41_B64_MOVIE_SUBS_CAK.zip`: 3 dialogue movie CAK assets, SHA-256 `bf9f4e80ed4ea283829f6ab8b108c492a294c528ed76adbcd255f20dc98ac89a`

Every contained replacement body matches the exact replacement SHA recorded in the production/patch manifests: 30/30 PASS. Every pristine source asset was also re-extracted at its frozen LBA and size and matched its source SHA: 30/30 PASS.

## Story group

The 27 new event MES files occupy 972 sectors in total, but only 156 sectors actually change. This is expected for the fixed-layout MES compiler: most file bytes, control structures and unused regions are preserved.

B51 covers nine files: EV04001, EV04002, EV04003, EV04005, EV04020, EV04022, EV04050, EV04053 and EV04055. Their combined footprint is 324 sectors and their actual delta is 59 sectors.

B52 covers eighteen files: EV05001, EV05002, EV05003, EV05004, EV05005, EV05007, EV05010, EV05018, EV05019, EV05020, EV05021, EV05022, EV05023, EV05025, EV05026, EV05027, EV05051 and EV05052. Their combined footprint is 648 sectors and their actual delta is 97 sectors.

## Movie group

Three B64 movies were recovered as exact fixed-size CAK candidates:

- SK2MV_10.CAK — LBA 124497, 9,411,120 bytes, 13 subtitle events, 4,596 changed sectors.
- SK2MV_11.CAK — LBA 129093, 11,007,384 bytes, 10 subtitle events, 5,375 changed sectors.
- SK2MV_30.CAK — LBA 134468, 7,830,436 bytes, 10 subtitle events, 3,814 changed sectors out of a 3,824-sector footprint.

The retained B64 validation says the source audio ADX stream is byte-identical in each replacement. The source and replacement audio durations are preserved. The video candidate is 288x144 Cinepak at 20 fps instead of source 30 fps so that the re-encoded subtitled video plus unchanged ADX remains inside the original fixed file allocation. There are 33 subtitle events across these three files.

SK2MV_31 remains deliberately unmodified because the historical B64 audit classified it as a no-dialogue movie for which subtitle replacement was not required.

## Pristine raw-sector anomaly and corrected preservation policy

During source-sector validation, pristine LBA 250901 was found to be a valid MODE1 sector with correct sync, mode, EDC, reserved bytes and ECC-P, but an ECC-Q mismatch. The pristine raw sector is the authoritative Expected Write source and this defect predates the patch.

Batch240 therefore does not rewrite a sector merely to normalize its ECC. When candidate 2048-byte user data is unchanged, the full pristine/parent raw sector is retained byte-for-byte. When candidate user data differs, that sector is rebuilt and the resulting EDC, ECC-P and ECC-Q must all pass. This avoids turning an unrelated source-disc defect into a patch delta.

Only one such pristine anomaly exists in the complete 14,767-sector footprint of this Batch240 target set: LBA 250901.

## Physical union verification

Authoritative parent:

- Batch239 assets: 64
- parent SHA-256: `daa1052fabd4142feaf42f14bdb5deefdf486cea8f0db8c939fc18ce6f822a56`
- parent changed sectors from pristine: 1,901

New target footprint:

- assets: 30
- footprint sectors: 14,767
- actual changed sectors: 13,941
- overlap with Batch239 changed sectors: 0
- changes outside approved footprints: 0

Final result:

- previous 64 physical assets preserved: 64/64 PASS
- new assets re-extracted: 30/30 PASS
- total physical assets: 94/94 PASS
- changed sectors from pristine: 15,842 = 1,901 + 13,941
- every one of the 15,842 changed output sectors passes MODE1 EDC/ECC
- final Disc SHA-256: `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83`

The full Disc remains a local verification artifact and is not committed or distributed.

## Production components

- `tools/integrate_batch239_promoted30_batch240.py`
- `manifests/CD1_BATCH239_PROMOTED30_UNION_BATCH240.json`
- this report

The next physical parent is the Batch240 SHA above. Work should continue in large groups: recover additional already-produced movie/story/UI payload packages, prove their source/candidate hashes and footprints against the pristine Disc and Batch240 parent, and only then add them to the lineage under Expected Write, overlap, changed-sector, EDC/ECC and whole-asset re-extraction gates.
