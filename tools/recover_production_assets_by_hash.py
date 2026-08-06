#!/usr/bin/env python3
"""Recover exact CD1 story/movie replacement assets from loose files and ZIPs.

No filename trust and no payload inference: candidates are accepted only when
size and SHA-256 match CD1_PRODUCTION_STORY_MOVIE_TARGETS.json. Duplicate
hashes are allowed only when their bytes are identical, enabling one payload to
satisfy repeated assets such as EV05003/EV05010.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

CHUNK = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def load_manifest(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding='utf-8'))
    disc = doc.get('source_disc', {})
    assets = doc.get('assets', [])
    if doc.get('format') != 'st2-disc1-production-assets-v1':
        raise ValueError('unsupported manifest format')
    if int(disc.get('size', 0)) != 659293824:
        raise ValueError('unexpected source Disc size')
    if disc.get('sha256') != 'd6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106':
        raise ValueError('unexpected source Disc SHA-256')
    if not assets:
        raise ValueError('empty asset list')
    seen = set()
    for a in assets:
        path_key = a['iso_path']
        if path_key in seen:
            raise ValueError(f'duplicate iso_path: {path_key}')
        seen.add(path_key)
        if int(a['size']) <= 0:
            raise ValueError(f'invalid size: {path_key}')
        for key in ('source_sha256', 'replacement_sha256'):
            value = str(a[key]).lower()
            if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError(f'invalid {key}: {path_key}')
    scope = doc.get('scope', {})
    if int(scope.get('asset_count', -1)) != len(assets):
        raise ValueError('scope asset_count mismatch')
    return doc


def wanted_index(doc: dict) -> dict[tuple[int, str], list[dict]]:
    out: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for a in doc['assets']:
        out[(int(a['size']), a['replacement_sha256'].lower())].append(a)
    return out


def iter_candidates(roots: list[Path]):
    for root in roots:
        if root.is_file():
            paths = [root]
        elif root.is_dir():
            paths = sorted(p for p in root.rglob('*') if p.is_file())
        else:
            continue
        for path in paths:
            if path.suffix.lower() == '.zip':
                try:
                    with zipfile.ZipFile(path) as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            yield ('zip', path, info.filename, info.file_size, zf.read(info))
                except (zipfile.BadZipFile, OSError):
                    continue
            else:
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                yield ('file', path, None, size, None)


def recover(manifest: Path, roots: list[Path], output: Path | None) -> dict:
    doc = load_manifest(manifest)
    wanted = wanted_index(doc)
    found: dict[str, dict] = {}
    scanned_files = scanned_zip_entries = 0
    for kind, container, member, size, data in iter_candidates(roots):
        if not any(key[0] == size for key in wanted):
            continue
        if kind == 'file':
            scanned_files += 1
            digest = sha256_file(container)
            payload = None
        else:
            scanned_zip_entries += 1
            digest = sha256_bytes(data)
            payload = data
        matches = wanted.get((size, digest), [])
        for asset in matches:
            iso = asset['iso_path']
            if iso in found:
                continue
            record = {'iso_path': iso, 'size': size, 'sha256': digest,
                      'source': str(container), 'member': member}
            found[iso] = record
            if output is not None:
                target = output / 'ASSETS' / iso
                target.parent.mkdir(parents=True, exist_ok=True)
                if kind == 'file':
                    target.write_bytes(container.read_bytes())
                else:
                    target.write_bytes(payload)
                if sha256_file(target) != digest:
                    raise RuntimeError(f'write verification failed: {iso}')
    missing = [a['iso_path'] for a in doc['assets'] if a['iso_path'] not in found]
    result = {
        'format': 'st2-cd1-production-recovery-result-v1',
        'manifest': str(manifest),
        'manifest_asset_count': len(doc['assets']),
        'recovered_asset_count': len(found),
        'missing_asset_count': len(missing),
        'status': 'PASS_EXACT_PRODUCTION_ASSETS_RECOVERED' if not missing else 'BLOCKED_EXACT_REPLACEMENT_BYTES_MISSING',
        'found': [found[k] for k in sorted(found)],
        'missing': missing,
        'scan': {'loose_candidates_hashed': scanned_files, 'zip_entries_hashed': scanned_zip_entries},
        'safety': {
            'filename_trusted': False,
            'replacement_size_required': True,
            'replacement_sha256_required': True,
            'estimated_bytes_used': False,
            'disc_write_performed': False,
        },
    }
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / 'recovery_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def selftest() -> dict:
    disc = {'size':659293824,'sha256':'d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106','raw_sector_size':2352,'user_offset':16,'user_size':2048}
    payload = b'exact-production-asset'
    asset = {'iso_path':'SAKURA2/TEST.MES','lba':1,'size':len(payload),'source_sha256':'1'*64,'replacement_sha256':sha256_bytes(payload),'category':'story','group':'TEST'}
    doc = {'format':'st2-disc1-production-assets-v1','goal':'CD1_100_PERCENT','source_disc':disc,'scope':{'asset_count':1},'assets':[asset]}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); manifest = root/'m.json'; manifest.write_text(json.dumps(doc), encoding='utf-8')
        with zipfile.ZipFile(root/'p.zip','w') as zf: zf.writestr('renamed.bin', payload)
        result = recover(manifest, [root], root/'out')
        ok = result['status'].startswith('PASS') and (root/'out/ASSETS/SAKURA2/TEST.MES').read_bytes() == payload
    return {'status':'PASS' if ok else 'FAIL','recovered_asset_count':result['recovered_asset_count']}


def main() -> int:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    r=sub.add_parser('recover'); r.add_argument('manifest',type=Path); r.add_argument('roots',nargs='+',type=Path); r.add_argument('--output',type=Path)
    v=sub.add_parser('validate-manifest'); v.add_argument('manifest',type=Path)
    sub.add_parser('selftest'); a=p.parse_args()
    if a.cmd=='selftest': result=selftest()
    elif a.cmd=='validate-manifest':
        doc=load_manifest(a.manifest); result={'status':'PASS','asset_count':len(doc['assets']),'scope':doc['scope']}
    else: result=recover(a.manifest,a.roots,a.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'].startswith('PASS') else 2

if __name__=='__main__': raise SystemExit(main())
