# Sakura Taisen 2 Disc 1 Patch Project

- Goal: CD1 Korean patch candidate 100%
- Exact battle/static physical recovery: 58/58
- Exact large-story SK05/SKCM physical integration: 6/6
- Exact promoted B51/B52 story integration: 27/27
- Exact B64 subtitle movie integration: 3/3
- Current exact physical union: 94 assets
- Authoritative workflow: one `main` lineage only; parallel workflows forbidden

## Current batch

### Batch 240 — PASS PHYSICAL UNION 94/94

Batch240 physically unions the exact Batch239 64-asset parent with 30 retained historical payloads: nine B51 event MES files, eighteen B52 event MES files and three B64 subtitled CAK movies.

## Authoritative source and parent

- pristine Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Batch239 parent SHA-256: `daa1052fabd4142feaf42f14bdb5deefdf486cea8f0db8c939fc18ce6f822a56`
- Batch239 physical assets: `64`
- Batch239 changed sectors: `1,901`

## Recovered Batch240 packages

- B51 9 MES: `ST2R41_B51_MES.zip` SHA-256 `a513b7d127112070ccecec9af11f42c6ed878611373b3e47616ed6f153cac8e3`
- B52 18 MES: `ST2R41_B52_MES.zip` SHA-256 `26952e76b5966166b669d386460c55845a5a936c96bc07a71b14679a995458fd`
- B64 3 CAK: `ST2R41_B64_MOVIE_SUBS_CAK.zip` SHA-256 `bf9f4e80ed4ea283829f6ab8b108c492a294c528ed76adbcd255f20dc98ac89a`

Source SHA and replacement SHA: `30/30 PASS`.

## Batch240 physical result

- new assets: `30/30 PASS`
- new story assets: `27`
- new movie assets: `3`
- B64 subtitle events: `33`
- B64 audio ADX: byte-identical according to retained validation
- new approved footprint: `14,767` sectors
- new actual changed sectors: `13,941`
- parent/new overlap: `0`
- outside-footprint changes: `0`
- new re-extraction: `30/30 PASS`
- previous parent assets preserved/re-extracted: `64/64 PASS`
- total physical assets: `94/94 PASS`
- total changed sectors from pristine: `15,842`
- changed-sector MODE1 EDC/ECC: `15,842/15,842 PASS`
- final Disc SHA-256: `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83`

## Pristine raw-sector exception policy

Pristine LBA `250901` has valid sync/mode/EDC/reserved/ECC-P but historical ECC-Q mismatch. It is not a patch-created error. Batch240 preserves this raw sector byte-for-byte when its user data is unchanged; source-sector defects are never rewritten solely to normalize ECC. Every sector whose user data is changed by the patch is rebuilt and must pass EDC, ECC-P and ECC-Q.

## Current production components

- `tools/integrate_batch239_promoted30_batch240.py`
- `manifests/CD1_BATCH239_PROMOTED30_UNION_BATCH240.json`
- `reports/BATCH240_REPORT.md`

## Mandatory safety policy

- no estimated/inferred payload bytes;
- exact source and candidate SHA-256;
- raw-sector Expected Write before writes;
- actual changes only inside approved footprints;
- preserve unrelated pristine raw-sector anomalies;
- EDC/ECC on every changed sector;
- changed-sector accounting;
- exact whole-asset re-extraction;
- no copyrighted game/font/movie/full-Disc bytes committed.

## Next production priority

Use Batch240 SHA `dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83` as the only physical parent. Recover the remaining already-produced movie/story/UI packages from File Library in large groups and add them only after exact source/candidate SHA, footprint overlap, Expected Write, changed-sector EDC/ECC and whole-asset re-extraction gates pass.
