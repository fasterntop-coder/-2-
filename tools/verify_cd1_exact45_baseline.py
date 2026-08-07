#!/usr/bin/env python3
import argparse, hashlib, json, sys
from pathlib import Path

HEX = set('0123456789abcdef')
REQUIRED_NEW = {'SYS03','SYS02','SYS05','SYS08','SYS17','SYS07'}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def valid_sha(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX

def fail(msg):
    print(f'FAIL: {msg}', file=sys.stderr)
    raise SystemExit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--asset-dir', type=Path)
    args = ap.parse_args()
    doc = json.loads(args.manifest.read_text(encoding='utf-8'))
    if doc.get('status') != 'PASS_EXACT45_BASELINE_PROMOTED': fail('status')
    if doc.get('asset_count') != 45 or doc.get('asset_total') != 58: fail('coverage geometry')
    assets = doc.get('added_assets')
    if not isinstance(assets, list) or len(assets) != 6: fail('added asset count')
    names = {x.get('name') for x in assets if isinstance(x, dict)}
    if names != REQUIRED_NEW: fail('added asset names')
    for x in assets:
        if not isinstance(x.get('size'), int) or x['size'] <= 0: fail(f"size {x.get('name')}")
        if not valid_sha(x.get('sha256')): fail(f"sha {x.get('name')}")
        if args.asset_dir:
            p = args.asset_dir / f"{x['name']}.MES"
            if not p.is_file(): fail(f'missing {p}')
            if p.stat().st_size != x['size']: fail(f'size mismatch {p}')
            if sha256_file(p) != x['sha256']: fail(f'sha mismatch {p}')
    ev = doc.get('added_evidence', {})
    if ev.get('lba_conflicts') != 0: fail('lba conflicts')
    if ev.get('mode1_edc_ecc') != 'PASS': fail('EDC/ECC')
    if ev.get('whole_disc_diff_limited_to_target_lbas') is not True: fail('write scope')
    if ev.get('reextraction') != '19/19 PASS': fail('reextraction')
    if doc.get('gates', {}).get('estimated_bytes') != 0: fail('estimated bytes')
    print('PASS_EXACT45_BASELINE_45_OF_58_77_6_PERCENT')

if __name__ == '__main__':
    main()
