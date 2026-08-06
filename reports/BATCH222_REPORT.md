# Batch 222 — LBA 208689 legacy override supersession

## Result

`PASS_LBA208689_SUPERSEDED_BY_EXACT_STNSYS03`

Batch221의 실제 통합 후보를 순정 Disc에서 다시 재현했다.

- Batch221 후보 SHA-256: `e335f7e821821191bc7ecf6776b489949dac4dfe0e1ccdea6f7df8217053c6d8`
- 후보 크기: `659,293,824`
- 정적 21자산 + SK0306 + SK2MV_05 재추출: `23/23 PASS`

## Conflict found

기존 필수 legacy sector 규칙의 LBA `208689`는 최신 정확 자산 `STNSYS03`의 전체 extent `208663..208703` 안에 있다.

- 현재 정확 sector SHA-256: `3da035f48eb2cdd51b4248b5881b1fe2f30f0779234ce553eca7387286df0246`
- 구 Batch55 sector SHA-256: `97f604cdb474ebf374e5d95d0d1b77c8fa06816b207f44cb71dfd6893f66b2b0`
- 정확 STNSYS03 SHA-256: `70a624feeca087f10cfc82f929d4d80aeb21f45642c2d1996ab6a967aa48297d`
- 구 sector를 덮어쓴 뒤 STNSYS03 SHA-256: `73227bd7592868ea8260abc3f53c65847d769c432d2ece73fb12a0f5c153839a`

따라서 구 sector를 최신 후보에 적용하면 정확 STNSYS03 자산을 손상시킨다.

## Policy correction

- 정확 whole-asset extent가 legacy raw-sector 규칙보다 우선한다.
- STNSYS03 정확 자산이 있는 후보에서는 LBA 208689 구 override를 금지한다.
- Expected Write는 현재 정확 sector가 유지되는지 확인한다.
- 추정 바이트: 0
- Disc 쓰기: 0

## Added

- `manifests/CD1_LEGACY_SECTOR_LBA208689_SUPERSEDED.json`
- `tools/verify_lba208689_supersession.py`
