#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
B247_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
EXPECTED=['BATCH50_PATCH_MANIFEST.json','BATCH51_PATCH_MANIFEST.json','BATCH52_PATCH_MANIFEST.json','BATCH53_PATCH_MANIFEST.json','BATCH54_PATCH_MANIFEST.json','BATCH55_PATCH_MANIFEST.json']
EXPECTED_COUNTS=[6,9,18,19,8,15]

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()

def main()->int:
    ap=argparse.ArgumentParser(description='Build exact 75-asset Disc1 story mega manifest from B50-B55 manifests')
    ap.add_argument('--manifest-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=Path('manifests/CD1_BATCH249_STORY75_MEGA_PROMOTION.json'))
    a=ap.parse_args()
    merged={}
    provenance=[]
    for name,count in zip(EXPECTED,EXPECTED_COUNTS):
        p=a.manifest_dir/name
        if not p.is_file(): raise SystemExit(f'missing source manifest: {p}')
        o=json.loads(p.read_text(encoding='utf-8'))
        if o.get('target_disc')!=1 or o.get('parent_bin_sha256')!=PRISTINE_SHA: raise SystemExit(f'bad lineage: {name}')
        xs=o.get('replacement_files',[])
        if len(xs)!=count: raise SystemExit(f'cardinality mismatch {name}: {len(xs)} != {count}')
        provenance.append({'name':name,'sha256':sha256_file(p),'asset_count':count,'format':o.get('format')})
        for x in xs:
            key=x['iso_path']
            canonical={k:x[k] for k in ('iso_path','lba','size','source_sha256','replacement_sha256')}
            if key in merged and merged[key]!=canonical: raise SystemExit(f'conflicting duplicate: {key}')
            merged[key]=canonical
    assets=sorted(merged.values(),key=lambda x:(x['lba'],x['iso_path']))
    if len(assets)!=75: raise SystemExit(f'unique story asset count {len(assets)} != 75')
    names=[Path(x['iso_path']).name for x in assets]
    if len(set(names))!=75: raise SystemExit('duplicate basenames in story75')
    out={
      'format':'ST2-CD1-BATCH249-STORY75-MEGA-PROMOTION-v1','target_disc':1,
      'physical_parent_batch':247,'physical_parent_disc_sha256':B247_SHA,
      'pristine_disc_sha256':PRISTINE_SHA,'source_manifests':provenance,
      'asset_count':75,'replacement_files':assets,
      'policy':{'guessed_payload_bytes':False,'require_exact_candidate_sha256':True,'require_pristine_source_sha256':True,'require_parent_footprint_nonoverlap':True,'require_expected_write':True,'require_changed_sector_edc_ecc':True,'require_changed_sector_accounting':True,'require_whole_asset_reextraction':True},
      'status':'READY_FOR_EXACT_PAYLOAD_RECOVERY_AND_PHYSICAL_PROMOTION'
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','asset_count':75,'output':str(a.output),'source_manifest_count':6},ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
