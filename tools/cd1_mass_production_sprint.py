#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH244_MANIFEST = ROOT / 'manifests/CD1_BATCH244_EVENT34_PROMOTION.json'
VIDEO9_MANIFEST = ROOT / 'manifests/CD1_BATCH241_VIDEO9_RECOVERY_GATE.json'
PARENT_SHA = 'dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83'
PRISTINE_SHA = 'd6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def target_specs() -> dict[str, dict]:
    b244 = load_json(BATCH244_MANIFEST)
    v9 = load_json(VIDEO9_MANIFEST)
    if b244['physical_parent_disc_sha256'] != PARENT_SHA:
        raise SystemExit('Batch244 parent SHA drift')
    if v9['physical_parent_disc_sha256'] != PARENT_SHA:
        raise SystemExit('Video9 parent SHA drift')
    if b244['pristine_disc_sha256'] != PRISTINE_SHA or v9['pristine_disc_sha256'] != PRISTINE_SHA:
        raise SystemExit('pristine SHA drift')

    out: dict[str, dict] = {}
    for x in b244['replacement_files']:
        name = Path(x['iso_path']).name
        out[name] = {
            'group': 'EVENT34', 'name': name, 'size': x['size'],
            'replacement_sha256': x['replacement_sha256'], 'lba': x['lba']
        }
    for x in v9['direct_candidates']:
        out[x['asset']] = {
            'group': 'VIDEO9', 'name': x['asset'], 'size': x['size'],
            'replacement_sha256': x['replacement_sha256'], 'lba': x['lba']
        }
    # legacy ZIP-contained video assets have package SHA rather than standalone payload SHA.
    for x in v9['legacy_packages']:
        out['@ZIP:' + x['package']] = {
            'group': 'VIDEO9_ZIP', 'name': x['package'], 'size': None,
            'replacement_sha256': x['sha256'], 'asset': x['expected_asset'], 'lba': x['lba']
        }
    if len([x for x in out.values() if x['group'] == 'EVENT34']) != 34:
        raise SystemExit('EVENT34 cardinality drift')
    if len([x for x in out.values() if x['group'].startswith('VIDEO9')]) != 9:
        raise SystemExit('VIDEO9 cardinality drift')
    return out


def candidate_files(roots: list[Path]):
    exts = {'.mes', '.cak', '.zip'}
    for root in roots:
        if root.is_file():
            yield root
        elif root.is_dir():
            for p in root.rglob('*'):
                if p.is_file() and p.suffix.lower() in exts:
                    yield p


def inspect_zip(path: Path, by_name: dict[str, dict]) -> list[dict]:
    hits = []
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                spec = by_name.get(name)
                if not spec or spec['group'] == 'VIDEO9_ZIP':
                    continue
                if spec['size'] is not None and info.file_size != spec['size']:
                    continue
                data = zf.read(info)
                got = hashlib.sha256(data).hexdigest()
                if got == spec['replacement_sha256']:
                    hits.append({'target': name, 'group': spec['group'], 'container': str(path),
                                 'member': info.filename, 'sha256': got, 'size': len(data)})
    except (zipfile.BadZipFile, OSError):
        pass
    return hits


def inspect_path(path: Path, specs: dict[str, dict]) -> list[dict]:
    hits = []
    name = path.name
    direct = specs.get(name)
    zip_spec = specs.get('@ZIP:' + name)
    if direct and direct['group'] != 'VIDEO9_ZIP':
        if direct['size'] is None or path.stat().st_size == direct['size']:
            got = sha256_file(path)
            if got == direct['replacement_sha256']:
                hits.append({'target': name, 'group': direct['group'], 'container': str(path),
                             'member': None, 'sha256': got, 'size': path.stat().st_size})
    if zip_spec:
        got = sha256_file(path)
        if got == zip_spec['replacement_sha256']:
            hits.append({'target': '@ZIP:' + name, 'group': 'VIDEO9_ZIP', 'container': str(path),
                         'member': None, 'sha256': got, 'size': path.stat().st_size,
                         'asset': zip_spec['asset']})
    if path.suffix.lower() == '.zip':
        hits.extend(inspect_zip(path, specs))
    return hits


def run(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {'cmd': cmd, 'returncode': p.returncode, 'stdout': p.stdout[-8000:], 'stderr': p.stderr[-8000:]}


def main() -> int:
    ap = argparse.ArgumentParser(description='High-throughput exact-payload recovery/orchestration for ST2 Disc1. No guessed bytes.')
    ap.add_argument('roots', nargs='+', type=Path, help='Archive/candidate directories or files to scan recursively')
    ap.add_argument('--out', type=Path, default=ROOT / 'CD1_SPRINT_RECOVERY')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--parent-bin', type=Path, help='Exact Batch240 BIN; enables promotion only after SHA gate')
    ap.add_argument('--pristine-bin', type=Path, help='Exact pristine Disc1 BIN; enables source Expected Write gate')
    ap.add_argument('--promote', action='store_true', help='Run existing physical integrators only when their entire group is exact-complete')
    args = ap.parse_args()

    specs = target_specs()
    args.out.mkdir(parents=True, exist_ok=True)
    paths = list(candidate_files(args.roots))
    hits = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(inspect_path, p, specs) for p in paths]
        for fut in as_completed(futs):
            hits.extend(fut.result())

    # deterministic de-duplication: first lexical source wins; all sources remain in evidence list.
    hits.sort(key=lambda x: (x['target'], x['container'], x.get('member') or ''))
    found = {}
    for h in hits:
        found.setdefault(h['target'], h)

    event_targets = sorted(k for k, v in specs.items() if v['group'] == 'EVENT34')
    video_targets = sorted(k for k, v in specs.items() if v['group'].startswith('VIDEO9'))
    event_found = [x for x in event_targets if x in found]
    video_found = [x for x in video_targets if x in found]

    promotion = []
    parent_ok = pristine_ok = False
    if args.parent_bin and args.parent_bin.is_file():
        parent_ok = sha256_file(args.parent_bin) == PARENT_SHA
    if args.pristine_bin and args.pristine_bin.is_file():
        pristine_ok = sha256_file(args.pristine_bin) == PRISTINE_SHA

    if args.promote and parent_ok and pristine_ok:
        # Existing tools retain Expected Write, EDC/ECC, accounting and whole-asset re-extraction gates.
        if len(event_found) == 34:
            promotion.append({'group': 'EVENT34', 'status': 'READY_EXACT_INPUTS',
                              'next_tool': 'tools/integrate_batch244_event34.py'})
        if len(video_found) == 9:
            promotion.append({'group': 'VIDEO9', 'status': 'READY_EXACT_INPUTS',
                              'next_tool': 'tools/integrate_batch241_video9_batch242.py'})
    elif args.promote:
        promotion.append({'status': 'BLOCKED_PARENT_OR_PRISTINE_SHA', 'parent_ok': parent_ok, 'pristine_ok': pristine_ok})

    result = {
        'format': 'ST2-CD1-MASS-PRODUCTION-SPRINT-v1',
        'policy': {
            'guessed_bytes': False,
            'parent_sha256': PARENT_SHA,
            'pristine_sha256': PRISTINE_SHA,
            'promotion_delegates_to_existing_expected_write_edc_ecc_reextraction_gates': True
        },
        'scan': {'files_considered': len(paths), 'workers': max(1, args.workers), 'exact_hits': len(hits)},
        'event34': {'found': len(event_found), 'total': 34, 'missing': [x for x in event_targets if x not in found]},
        'video9': {'found': len(video_found), 'total': 9, 'missing': [x for x in video_targets if x not in found]},
        'evidence': hits,
        'promotion': promotion
    }
    out = args.out / 'CD1_SPRINT_RESULT.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
