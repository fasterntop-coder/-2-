#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

RAW_SECTOR = 2352
USER_OFF = 16
USER_SIZE = 2048
SYNC = bytes.fromhex('00FFFFFFFFFFFFFFFFFFFF00')
HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE.parent / 'manifests' / 'CD1_STORY_REBUILD_INPUTS_BATCH232.json'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_mode1_asset(disc: Path, lba: int, size: int) -> bytes:
    out = bytearray()
    remain = size
    with disc.open('rb') as f:
        sector = lba
        while remain:
            f.seek(sector * RAW_SECTOR)
            raw = f.read(RAW_SECTOR)
            if len(raw) != RAW_SECTOR:
                raise ValueError(f'short raw sector at LBA {sector}')
            if raw[:12] != SYNC or raw[15] != 1:
                raise ValueError(f'not MODE1/2352 at LBA {sector}')
            take = min(USER_SIZE, remain)
            out.extend(raw[USER_OFF:USER_OFF + take])
            remain -= take
            sector += 1
    return bytes(out)


def ledger_target(ledger: dict, target: dict) -> dict:
    if target.get('ledger_key'):
        files = ledger.get('files')
        if not isinstance(files, dict) or target['ledger_key'] not in files:
            raise ValueError(f"ledger key missing: {target['ledger_key']}")
        return files[target['ledger_key']]
    return ledger


def validate_ledger(path: Path, target: dict) -> dict:
    obj = json.loads(path.read_text(encoding='utf-8'))
    node = ledger_target(obj, target)
    source = node.get('source', node)
    compile_node = node.get('compile', node)
    got_source = source.get('sha256') or node.get('source_sha256') or compile_node.get('source_sha256')
    got_compiled = compile_node.get('compiled_sha256') or node.get('compiled_sha256')
    records = node.get('records')
    record_count = len(records) if isinstance(records, list) else node.get('message_count') or node.get('records_reviewed')
    return {
        'path': str(path),
        'source_sha256_match': got_source == target['source_sha256'],
        'compiled_sha256_match': got_compiled == target['compiled_sha256'],
        'record_count': record_count,
        'record_count_match': record_count == target['records'],
        'has_translation_records': isinstance(records, list) and len(records) == target['records'],
    }


def scan_exact_candidates(root: Path, expected: dict[str, dict]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        low = p.suffix.lower()
        try:
            if low == '.zip':
                with zipfile.ZipFile(p) as zf:
                    for zi in zf.infolist():
                        if zi.is_dir() or zi.file_size > 4 * 1024 * 1024:
                            continue
                        data = zf.read(zi)
                        h = sha256_bytes(data)
                        if h in expected and expected[h]['name'] not in found:
                            found[expected[h]['name']] = {'type':'zip_member','container':str(p),'member':zi.filename,'sha256':h,'size':len(data)}
            elif p.stat().st_size <= 4 * 1024 * 1024:
                h = sha256_file(p)
                if h in expected and expected[h]['name'] not in found:
                    found[expected[h]['name']] = {'type':'file','path':str(p),'sha256':h,'size':p.stat().st_size}
        except (OSError, zipfile.BadZipFile):
            continue
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description='Batch232 exact story rebuild/recovery preparation gate')
    ap.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument('--disc', type=Path)
    ap.add_argument('--font', type=Path)
    ap.add_argument('--ledger-dir', type=Path)
    ap.add_argument('--candidate-root', type=Path)
    ap.add_argument('--out-dir', type=Path, default=Path('BATCH232_OUTPUT'))
    args = ap.parse_args()

    mf = json.loads(args.manifest.read_text(encoding='utf-8'))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    result = {'batch':232,'status':'BLOCKED','disc':None,'font':None,'targets':{},'exact_candidates':{}}

    disc_ok = False
    if args.disc and args.disc.is_file():
        h = sha256_file(args.disc)
        disc_ok = args.disc.stat().st_size == mf['source_disc']['size'] and h == mf['source_disc']['sha256']
        result['disc'] = {'path':str(args.disc),'size':args.disc.stat().st_size,'sha256':h,'match':disc_ok}

    font_ok = False
    if args.font and args.font.is_file():
        h = sha256_file(args.font)
        font_ok = h == mf['font']['sha256']
        result['font'] = {'path':str(args.font),'sha256':h,'match':font_ok}

    expected_compiled = {t['compiled_sha256']:t for t in mf['targets']}
    if args.candidate_root and args.candidate_root.exists():
        result['exact_candidates'] = scan_exact_candidates(args.candidate_root, expected_compiled)

    all_sources = True
    all_ledgers = True
    for t in mf['targets']:
        entry = {'source':None,'ledger':None,'exact_candidate':result['exact_candidates'].get(t['name'])}
        if disc_ok:
            data = extract_mode1_asset(args.disc, t['lba'], t['size'])
            sh = sha256_bytes(data)
            source_ok = sh == t['source_sha256'] and len(data) == t['size']
            entry['source'] = {'sha256':sh,'size':len(data),'match':source_ok}
            if source_ok:
                (args.out_dir / ('SOURCE_' + t['name'])).write_bytes(data)
            all_sources &= source_ok
        else:
            all_sources = False

        if args.ledger_dir:
            lp = args.ledger_dir / t['ledger']
            if lp.is_file():
                try:
                    entry['ledger'] = validate_ledger(lp, t)
                    all_ledgers &= all(entry['ledger'][k] for k in ('source_sha256_match','compiled_sha256_match','record_count_match','has_translation_records'))
                except Exception as exc:
                    entry['ledger'] = {'error':str(exc)}
                    all_ledgers = False
            else:
                entry['ledger'] = {'missing':str(lp)}
                all_ledgers = False
        else:
            all_ledgers = False
        result['targets'][t['name']] = entry

    recovered = len(result['exact_candidates'])
    if recovered == len(mf['targets']):
        result['status'] = 'PASS_ALL_SIX_EXACT_COMPILED_PAYLOADS_RECOVERED'
    elif disc_ok and font_ok and all_sources and all_ledgers:
        result['status'] = 'PASS_REBUILD_INPUTS_EXACT_COMPILER_EXECUTION_REQUIRED'
    else:
        missing = []
        if not disc_ok: missing.append('exact original Disc1 BIN')
        if not font_ok: missing.append('exact UnDotum.ttf')
        if not all_ledgers: missing.append('complete exact translation ledgers')
        if not all_sources: missing.append('source asset extraction proof')
        result['missing'] = missing

    out = args.out_dir / 'BATCH232_PREP_RESULT.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'].startswith('PASS_') else 2


if __name__ == '__main__':
    raise SystemExit(main())
