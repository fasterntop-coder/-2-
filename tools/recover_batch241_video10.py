#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_gate(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('format') != 'ST2-CD1-BATCH241-VIDEO10-RECOVERY-GATE-v1':
        raise SystemExit('unexpected gate format')
    return obj


def recover_from_trusted_zip(zip_path: Path, spec: dict, out_dir: Path) -> dict:
    actual = sha256_file(zip_path)
    if actual != spec['sha256']:
        raise SystemExit(f"trusted package SHA mismatch: {zip_path.name}: {actual}")
    expected_name = spec['expected_asset'].lower()
    matches = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if Path(info.filename).name.lower() != expected_name:
                continue
            data = zf.read(info)
            if len(data) != spec['size']:
                continue
            matches.append((info.filename, data))
    if len(matches) != 1:
        raise SystemExit(f"{zip_path.name}: expected exactly one {spec['expected_asset']} of size {spec['size']}, got {len(matches)}")
    member, data = matches[0]
    out = out_dir / spec['expected_asset']
    out.write_bytes(data)
    return {
        'asset': spec['expected_asset'],
        'source_package': zip_path.name,
        'source_package_sha256': actual,
        'source_member': member,
        'lba': spec['lba'],
        'size': len(data),
        'source_sha256': spec['source_sha256'],
        'replacement_sha256': sha256_bytes(data),
        'recovery_basis': 'exact trusted package SHA + exact member basename + exact asset size'
    }


def recover_direct(candidate_dir: Path, spec: dict, out_dir: Path) -> dict:
    src = candidate_dir / spec['asset']
    if not src.is_file():
        raise SystemExit(f"missing direct candidate: {src}")
    if src.stat().st_size != spec['size']:
        raise SystemExit(f"candidate size mismatch: {spec['asset']}")
    actual = sha256_file(src)
    if actual != spec['replacement_sha256']:
        raise SystemExit(f"candidate SHA mismatch: {spec['asset']}: {actual}")
    dst = out_dir / spec['asset']
    if src.resolve() != dst.resolve():
        shutil.copyfile(src, dst)
    return {
        'asset': spec['asset'],
        'lba': spec['lba'],
        'size': spec['size'],
        'source_sha256': spec['source_sha256'],
        'replacement_sha256': actual,
        'recovery_basis': 'exact standalone candidate SHA-256'
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Recover the remaining 10 exact Disc1 movie candidates without guessing bytes.')
    ap.add_argument('--gate', type=Path, default=Path('manifests/CD1_BATCH241_VIDEO10_RECOVERY_GATE.json'))
    ap.add_argument('--archive-dir', type=Path, required=True, help='Directory containing trusted ST2B65/66/67 ZIPs')
    ap.add_argument('--candidate-dir', type=Path, required=True, help='Directory containing exact B63/B64 CAK candidates')
    ap.add_argument('--output-dir', type=Path, default=Path('BATCH241_VIDEO10_RECOVERED'))
    ap.add_argument('--result', type=Path, default=Path('BATCH241_VIDEO10_RECOVERY_RESULT.json'))
    args = ap.parse_args()

    gate = load_gate(args.gate)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    recovered = []

    for spec in gate['legacy_packages']:
        z = args.archive_dir / spec['package']
        if not z.is_file():
            raise SystemExit(f"missing trusted package: {z}")
        recovered.append(recover_from_trusted_zip(z, spec, args.output_dir))

    for spec in gate['direct_candidates']:
        recovered.append(recover_direct(args.candidate_dir, spec, args.output_dir))

    names = [x['asset'] for x in recovered]
    if len(recovered) != 10 or len(set(names)) != 10:
        raise SystemExit('recovery cardinality mismatch')

    consolidated = {
        'format': 'ST2-CD1-BATCH241-VIDEO10-CONSOLIDATED-MANIFEST-v1',
        'physical_parent_batch': 240,
        'physical_parent_disc_sha256': gate['physical_parent_disc_sha256'],
        'pristine_disc_sha256': gate['pristine_disc_sha256'],
        'replacement_files': [
            {
                'iso_path': f"SAKURA1/{x['asset']}",
                'lba': x['lba'],
                'size': x['size'],
                'source_sha256': x['source_sha256'],
                'replacement_sha256': x['replacement_sha256']
            }
            for x in recovered
        ],
        'promotion_allowed': False,
        'promotion_block': 'Run physical-parent overlap, raw-sector Expected Write, changed-sector EDC/ECC, changed-sector accounting, and whole-asset re-extraction gates before any Disc write is promoted.'
    }
    manifest_path = args.output_dir / 'BATCH241_VIDEO10_CONSOLIDATED_MANIFEST.json'
    manifest_path.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2), encoding='utf-8')

    result = {
        'batch': 241,
        'status': 'PASS_EXACT_VIDEO10_RECOVERY_GATE_ONLY',
        'recovered_assets': len(recovered),
        'assets': recovered,
        'consolidated_manifest': str(manifest_path),
        'game_bytes_changed': 0,
        'guessed_payload_bytes': False,
        'physical_parent_sha256': gate['physical_parent_disc_sha256']
    }
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
