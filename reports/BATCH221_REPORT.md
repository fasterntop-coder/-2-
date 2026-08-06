# Batch 221 — Static21 + Batch60 actual runtime merge

## Result

- Status: `PASS_STATIC21_PLUS_BATCH60_RUNTIME_CANDIDATE`
- Pristine Disc SHA-256: `d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106`
- Static21 candidate SHA-256: `8ceff2afb22e080469ad1adcc8f84f85d45c6b5e838df101beba70f00e3b0861`
- Batch60 candidate SHA-256: `7f57743b947704963290e2e108485262c940690c4a3c8d60800a7ae3338f397d`
- Merged candidate SHA-256: `e335f7e821821191bc7ecf6776b489949dac4dfe0e1ccdea6f7df8217053c6d8`
- Merged changed raw sectors: `59,533`
- Changed-LBA-list SHA-256: `5bede6277aab6358d511518c595bb10d885f00bf5be5928815fbaf76ffac95d9`

## Conflict resolution

The two validated candidates overlapped in legacy combat-bank regions. Sector-level changed-byte priority was rejected because unchanged sectors inside a newer exact asset extent could still carry an older fallback version. The merge therefore reserves the complete extents of all 21 Static21 assets and copies those sectors byte-exactly from the newer candidate. Batch60 wins everywhere else.

- Reserved Static21 sectors: `846`
- Policy: `STATIC21_WINS_FOR_COMPLETE_21_ASSET_EXTENTS; BATCH60_WINS_ELSEWHERE`
- Estimated bytes: `0`

## Gates

- Static21 source EDC/ECC: `609/609 PASS`
- Batch60 source EDC/ECC: `59,051/59,051 PASS`
- Merged-sector provenance: every sector copied byte-exactly from an independently validated candidate
- Static assets re-extracted: `21/21 PASS`
- Additional newly checked runtime assets:
  - `SK0306.BIN` SHA-256 `0ce44542009f85613027ab9ebad0689398d24eed5c1998fd16170f50240e4ef3`
  - `SK2MV_05.CAK` SHA-256 `e1f11325e55066171f60caa7b9d9d3dfc928150d11723860be9e3e84c74c3f89`
- Total explicit re-extraction checks: `23/23 PASS`

## Progress table

| 기준 | CD1 | CD2 | CD3 | 전체 |
|---|---:|---:|---:|---:|
| 구현 기록 | 46.3% | 0% | 0% | 15.4% |
| 실기 확정 | 44.4% | 0% | 0% | 14.8% |
| 전투·정적 실제 후보 통합 | 21/58 · 36.2% | 0/58 · 0% | 0/58 · 0% | 21/174 · 12.1% |
| 스토리 정적 인벤토리 | 잔여 후보 0 · 정적 마감 | 0% | 0% | CD1 정적 마감 |
| 동영상 자막 정적 인벤토리 | 24/24 · 100% | 0% | 0% | 24/72 · 33.3% |
| 현재 실제 후보 추가 검증 | SK0306 + SK2MV_05 PASS | — | — | 2자산 |

The merged full BIN was deleted after hashing and re-extraction validation. No copyrighted Disc image was committed.
