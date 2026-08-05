#!/usr/bin/env python3
"""Recover exact ST2 assets from loose files, raw BIN checkpoints, or ZIPs.

Only assets whose complete SHA-256 equals a trusted target are emitted. Whole
Disc images are never copied or modified.
"""
from __future__ import annotations

import argparse, hashlib, io, json, tempfile, zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

CHUNK = 8 * 1024 * 1024


def sha_stream(f: BinaryIO) -> str:
    h = hashlib.sha256()
    while b := f.read(CHUNK): h.update(b)
    return h.hexdigest()


def sha_bytes(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def files(root: Path) -> Iterable[Path]: return (p for p in root.rglob('*') if p.is_file())


def accept(data: bytes, asset: dict, out: Path, source: str, found: dict) -> bool:
    if len(data) != asset['size'] or sha_bytes(data) != asset['target_sha256']: return False
    name = asset['name'] + '.MES'
    path = out / name
    if path.exists() and path.read_bytes() != data: raise RuntimeError(f'conflicting exact payload: {name}')
    path.write_bytes(data)
    found[asset['name']] = {'path': str(path), 'sha256': asset['target_sha256'], 'source': source}
    return True


def scan_binary(f: BinaryIO, size: int, label: str, assets: list[dict], raw: int, out: Path, found: dict) -> None:
    for a in assets:
        if a['name'] in found: continue
        f.seek(a['lba'] * raw)
        accept(f.read(a['size']), a, out, f'{label}@LBA{a["lba"]}', found)


def recover(manifest_path: Path, root: Path, out: Path) -> dict:
    m = json.loads(manifest_path.read_text(encoding='utf-8'))
    assets, disc, raw = m['assets'], m['source_disc'], m['source_disc']['raw_sector_size']
    out.mkdir(parents=True, exist_ok=True); found = {}
    target_by_size = {}
    for a in assets: target_by_size.setdefault(a['size'], []).append(a)

    for p in files(root):
        try:
            if p.suffix.lower() == '.zip':
                with zipfile.ZipFile(p) as z:
                    for i in z.infolist():
                        if i.is_dir(): continue
                        if i.file_size in target_by_size:
                            data = z.read(i)
                            for a in target_by_size[i.file_size]: accept(data, a, out, f'{p}!{i.filename}', found)
                        elif i.file_size == disc['size']:
                            with z.open(i) as member:
                                # ZipExtFile is seekable on current Python; spool if not.
                                if member.seekable(): scan_binary(member, i.file_size, f'{p}!{i.filename}', assets, raw, out, found)
                                else:
                                    with tempfile.TemporaryFile() as t:
                                        while b := member.read(CHUNK): t.write(b)
                                        scan_binary(t, i.file_size, f'{p}!{i.filename}', assets, raw, out, found)
            else:
                sz = p.stat().st_size
                if sz in target_by_size:
                    data = p.read_bytes()
                    for a in target_by_size[sz]: accept(data, a, out, str(p), found)
                elif sz == disc['size']:
                    with p.open('rb') as f: scan_binary(f, sz, str(p), assets, raw, out, found)
        except (OSError, zipfile.BadZipFile):
            continue

    missing = [a['name'] for a in assets if a['name'] not in found]
    result = {'status': 'PASS_ALL_EXACT_ASSETS_RECOVERED' if not missing else 'PARTIAL_EXACT_ASSET_RECOVERY',
              'recovered': found, 'missing': missing, 'recovered_count': len(found), 'target_count': len(assets)}
    (out/'RECOVERY_RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def selftest() -> dict:
    raw, disc_size = 64, 640
    a = bytes((i*7+3)&255 for i in range(17)); b = bytes((i*11+5)&255 for i in range(19))
    disc = bytearray(disc_size); disc[2*raw:2*raw+len(a)] = a
    manifest = {'source_disc': {'size': disc_size, 'raw_sector_size': raw}, 'assets': [
        {'name':'A','lba':2,'size':len(a),'target_sha256':sha_bytes(a)},
        {'name':'B','lba':5,'size':len(b),'target_sha256':sha_bytes(b)}]}
    with tempfile.TemporaryDirectory() as d:
        r=Path(d); (r/'disc.bin').write_bytes(disc)
        with zipfile.ZipFile(r/'loose.zip','w') as z: z.writestr('B.MES', b)
        mp=r/'m.json'; mp.write_text(json.dumps(manifest), encoding='utf-8')
        result=recover(mp,r,r/'out')
        ok=result['status']=='PASS_ALL_EXACT_ASSETS_RECOVERED' and (r/'out/A.MES').read_bytes()==a and (r/'out/B.MES').read_bytes()==b
    return {'status':'PASS' if ok else 'FAIL','roundtrip':ok}


def main() -> int:
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
    r=s.add_parser('recover'); r.add_argument('manifest',type=Path); r.add_argument('root',type=Path); r.add_argument('--output-dir',type=Path,default=Path('output/EXACT_ASSETS'))
    s.add_parser('selftest'); a=p.parse_args()
    result=selftest() if a.cmd=='selftest' else recover(a.manifest,a.root,a.output_dir)
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['status'].startswith('PASS') else 2

if __name__=='__main__': raise SystemExit(main())
