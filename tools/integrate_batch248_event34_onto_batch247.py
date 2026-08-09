#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

B247_SHA = 'd37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
B247_MANIFEST = Path('manifests/CD1_BATCH247_C2FIX_STATIC58_COMPOSITE.json')
BASE_TOOL = Path(__file__).with_name('integrate_batch244_event34.py')
DEFAULT_EVENT_MANIFEST = Path('manifests/CD1_BATCH244_EVENT34_PROMOTION.json')

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        while c := f.read(8 * 1024 * 1024):
            h.update(c)
    return h.hexdigest()

def load_base_tool():
    spec = importlib.util.spec_from_file_location('st2_b244_event34', BASE_TOOL)
    if spec is None or spec.loader is None:
        raise SystemExit('cannot load Batch244 integrator')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main() -> int:
    ap = argparse.ArgumentParser(description='Batch248: rebase exact 34 Event MES onto verified Batch247 C2FIX+Static58 parent')
    ap.add_argument('--pristine', type=Path, required=True)
    ap.add_argument('--parent', type=Path, required=True, help='Exact Batch247 output BIN')
    ap.add_argument('--candidate-dir', type=Path, required=True)
    ap.add_argument('--event-manifest', type=Path, default=DEFAULT_EVENT_MANIFEST)
    ap.add_argument('--batch247-manifest', type=Path, default=B247_MANIFEST)
    ap.add_argument('--output', type=Path, default=Path('Sakura_Taisen_2_Disc1_B248_C2FIX_STATIC58_EVENT34_KO.bin'))
    ap.add_argument('--result', type=Path, default=Path('BATCH248_RESULT.json'))
    a = ap.parse_args()

    lineage = json.loads(a.batch247_manifest.read_text(encoding='utf-8'))
    if lineage.get('format') != 'ST2-CD1-BATCH247-C2FIX-STATIC58-COMPOSITE-v1':
        raise SystemExit('unexpected Batch247 lineage manifest')
    if lineage.get('output', {}).get('bin_sha256') != B247_SHA:
        raise SystemExit('Batch247 manifest output SHA mismatch')
    if sha256_file(a.parent) != B247_SHA:
        raise SystemExit('Batch247 parent BIN SHA mismatch')

    mod = load_base_tool()
    mod.PARENT_SHA = B247_SHA

    temp_result = a.result.with_suffix('.b244tmp.json')
    old_argv = sys.argv[:]
    try:
        sys.argv = [
            str(BASE_TOOL),
            '--pristine', str(a.pristine),
            '--parent', str(a.parent),
            '--candidate-dir', str(a.candidate_dir),
            '--manifest', str(a.event_manifest),
            '--output', str(a.output),
            '--result', str(temp_result),
        ]
        rc = mod.main()
    finally:
        sys.argv = old_argv
    if rc != 0:
        return rc

    r = json.loads(temp_result.read_text(encoding='utf-8'))
    if r.get('status') != 'PASS_EVENT34_PHYSICAL_PROMOTION' or r.get('assets_promoted') != 34:
        a.output.unlink(missing_ok=True)
        raise SystemExit('underlying Event34 promotion did not pass')
    if r.get('parent_sha256') != B247_SHA:
        a.output.unlink(missing_ok=True)
        raise SystemExit('underlying parent lineage mismatch')

    out = {
        'batch': 248,
        'status': 'PASS_B247_PLUS_EVENT34_EXECUTABLE_CANDIDATE',
        'parent_batch': 247,
        'parent_sha256': B247_SHA,
        'parent_static_assets': '58/58',
        'event_assets_promoted': 34,
        'output_sha256': r['output_sha256'],
        'changed_sectors_vs_batch247': r['changed_sectors'],
        'expected_write_records': r['expected_write_records'],
        'parent_overlap': r['parent_overlap'],
        'outside_footprint_changes': r['outside_footprint_changes'],
        'changed_sector_edc_ecc': r['changed_sector_edc_ecc'],
        'whole_asset_reextraction': r['whole_asset_reextraction'],
        'safety': {
            'guessed_bytes': False,
            'exact_candidate_sha256': True,
            'exact_pristine_source_sha256': True,
            'batch247_full_sha_gate': True,
            'expected_write': True,
            'changed_sector_accounting': True,
        },
        'underlying_batch244_result': r,
    }
    a.result.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    temp_result.unlink(missing_ok=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
