#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEX64 = re.compile(r'^[0-9a-f]{64}$')
EXPECTED_PARENT = 'dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83'
EXPECTED_PRISTINE = 'd6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
EXPECTED_FORMAT = 'ST2-CD1-BATCH241-VIDEO9-RECOVERY-GATE-v2'
EXPECTED_ASSETS = {
    'SK2MV_04.CAK', 'SK2MV_05.CAK', 'SK2MV_06.CAK',
    'SK2MV_43.CAK', 'SK2MV_44.CAK', 'SK2MV_45.CAK',
    'SK2MV_46.CAK', 'SK2MV_47.CAK', 'SK2MV_48.CAK',
}
REQUIRED_POLICY_TRUE = {
    'require_candidate_sha_before_physical_write',
    'require_expected_write',
    'require_changed_sector_edc_ecc',
    'require_whole_asset_reextraction',
}


def canonical_json(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_hex64(value: object, label: str) -> None:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise SystemExit(f'{label}: expected lowercase 64-hex SHA-256')


def load(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise SystemExit(f'{path}: invalid JSON: {exc}') from exc
    if not isinstance(obj, dict):
        raise SystemExit(f'{path}: root must be an object')
    return obj


def audit_gate(gate: dict) -> dict:
    if gate.get('format') != EXPECTED_FORMAT:
        raise SystemExit(f"format mismatch: {gate.get('format')!r}")
    if gate.get('physical_parent_batch') != 240:
        raise SystemExit('physical_parent_batch must be 240')
    if gate.get('physical_parent_disc_sha256') != EXPECTED_PARENT:
        raise SystemExit('Batch240 parent SHA mismatch')
    if gate.get('pristine_disc_sha256') != EXPECTED_PRISTINE:
        raise SystemExit('pristine Disc SHA mismatch')
    if gate.get('correction', {}).get('excluded_already_promoted_asset') != 'SK2MV_30.CAK':
        raise SystemExit('SK2MV_30 exclusion correction missing')

    policy = gate.get('policy')
    if not isinstance(policy, dict):
        raise SystemExit('policy object missing')
    if policy.get('guessed_payload_bytes') is not False:
        raise SystemExit('guessed_payload_bytes must be false')
    for key in REQUIRED_POLICY_TRUE:
        if policy.get(key) is not True:
            raise SystemExit(f'policy gate must be true: {key}')

    legacy = gate.get('legacy_packages')
    direct = gate.get('direct_candidates')
    if not isinstance(legacy, list) or len(legacy) != 3:
        raise SystemExit('legacy package cardinality must be 3')
    if not isinstance(direct, list) or len(direct) != 6:
        raise SystemExit('direct candidate cardinality must be 6')

    assets: list[str] = []
    lbas: list[int] = []
    for i, spec in enumerate(legacy):
        asset = spec.get('expected_asset')
        package = spec.get('package')
        if not isinstance(asset, str) or not isinstance(package, str):
            raise SystemExit(f'legacy[{i}]: asset/package missing')
        require_hex64(spec.get('sha256'), f'legacy[{i}].package_sha256')
        require_hex64(spec.get('source_sha256'), f'legacy[{i}].source_sha256')
        if not isinstance(spec.get('lba'), int) or spec['lba'] < 0:
            raise SystemExit(f'legacy[{i}]: invalid LBA')
        if not isinstance(spec.get('size'), int) or spec['size'] <= 0:
            raise SystemExit(f'legacy[{i}]: invalid size')
        assets.append(asset)
        lbas.append(spec['lba'])

    for i, spec in enumerate(direct):
        asset = spec.get('asset')
        if not isinstance(asset, str):
            raise SystemExit(f'direct[{i}]: asset missing')
        require_hex64(spec.get('source_sha256'), f'direct[{i}].source_sha256')
        require_hex64(spec.get('replacement_sha256'), f'direct[{i}].replacement_sha256')
        if spec['source_sha256'] == spec['replacement_sha256']:
            raise SystemExit(f'direct[{i}]: source and replacement SHA unexpectedly identical')
        if not isinstance(spec.get('lba'), int) or spec['lba'] < 0:
            raise SystemExit(f'direct[{i}]: invalid LBA')
        if not isinstance(spec.get('size'), int) or spec['size'] <= 0:
            raise SystemExit(f'direct[{i}]: invalid size')
        assets.append(asset)
        lbas.append(spec['lba'])

    if len(assets) != 9 or len(set(assets)) != 9:
        raise SystemExit('asset set must contain 9 unique entries')
    if set(assets) != EXPECTED_ASSETS:
        raise SystemExit(f'asset set mismatch: {sorted(set(assets) ^ EXPECTED_ASSETS)}')
    if 'SK2MV_30.CAK' in assets:
        raise SystemExit('SK2MV_30.CAK is already promoted in Batch240 and must not re-enter')
    if len(set(lbas)) != len(lbas):
        raise SystemExit('duplicate LBA in recovery gate')

    return {
        'format': gate['format'],
        'physical_parent_disc_sha256': gate['physical_parent_disc_sha256'],
        'pristine_disc_sha256': gate['pristine_disc_sha256'],
        'asset_count': len(assets),
        'assets': sorted(assets),
        'excluded_already_promoted_asset': 'SK2MV_30.CAK',
        'manifest_semantic_sha256': sha256_bytes(canonical_json(gate)),
        'guessed_payload_bytes': False,
        'promotion_allowed': False,
        'status': 'PASS_BATCH241_VIDEO9_GATE_INVARIANTS',
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Audit Batch241 Video9 manifest invariants without touching game bytes.')
    ap.add_argument('--canonical', type=Path, default=Path('manifests/CD1_BATCH241_VIDEO9_RECOVERY_GATE.json'))
    ap.add_argument('--legacy-alias', type=Path, default=Path('manifests/CD1_BATCH241_VIDEO10_RECOVERY_GATE.json'))
    ap.add_argument('--result', type=Path)
    args = ap.parse_args()

    canonical = load(args.canonical)
    result = audit_gate(canonical)

    if args.legacy_alias.is_file():
        alias = load(args.legacy_alias)
        audit_gate(alias)
        if canonical_json(alias) != canonical_json(canonical):
            raise SystemExit('legacy Video10-named manifest diverges from canonical Video9 manifest')
        result['legacy_alias_semantically_identical'] = True
    else:
        result['legacy_alias_semantically_identical'] = None

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.result:
        args.result.write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
