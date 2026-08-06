#!/usr/bin/env python3
"""Merge two already-validated MODE1/2352 CD1 candidates by exact asset extents.

The preferred candidate wins for complete declared asset extents. Everywhere else
the fallback candidate wins. No estimated bytes are generated. Every output raw
sector is copied byte-exactly from one of the two input candidates.
"""
from __future__ import annotations
import argparse, hashlib, json, math, shutil
from pathlib import Path
RAW=2352
DISC_SIZE=659_293_824

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(16*1024*1024),b''): h.update(block)
    return h.hexdigest()

def extract(path: Path,lba:int,size:int)->bytes:
    out=bytearray(); remain=size
    with path.open('rb') as f:
        while remain:
            f.seek(lba*RAW+16); n=min(2048,remain); out+=f.read(n); remain-=n; lba+=1
    return bytes(out)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('pristine',type=Path); ap.add_argument('preferred',type=Path)
    ap.add_argument('fallback',type=Path); ap.add_argument('asset_manifest',type=Path)
    ap.add_argument('output',type=Path); ap.add_argument('--result',type=Path,default=Path('output/merge_result.json'))
    a=ap.parse_args(); manifest=json.loads(a.asset_manifest.read_text(encoding='utf-8'))
    for p in (a.pristine,a.preferred,a.fallback):
        if p.stat().st_size!=DISC_SIZE: raise SystemExit(f'bad disc size: {p}')
    assets=manifest['assets']; reserved=set()
    for x in assets:
        reserved.update(range(int(x['lba']),int(x['lba'])+math.ceil(int(x['size'])/2048)))
    shutil.copyfile(a.fallback,a.output)
    with a.preferred.open('rb') as src,a.output.open('r+b') as dst:
        for lba in sorted(reserved):
            src.seek(lba*RAW); sector=src.read(RAW); dst.seek(lba*RAW); dst.write(sector)
    checks=[]
    for x in assets:
        got=hashlib.sha256(extract(a.output,int(x['lba']),int(x['size']))).hexdigest()
        checks.append({'asset':x['asset'],'expected_sha256':x['sha256'],'actual_sha256':got,'status':'PASS' if got==x['sha256'] else 'FAIL'})
    status='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL'
    result={'status':status,'pristine_sha256':sha256_file(a.pristine),'preferred_sha256':sha256_file(a.preferred),'fallback_sha256':sha256_file(a.fallback),'output_sha256':sha256_file(a.output),'reserved_sector_count':len(reserved),'asset_checks':checks,'sector_provenance':'BYTE_EXACT_FROM_VALIDATED_INPUT_CANDIDATES','estimated_bytes':0}
    a.result.parent.mkdir(parents=True,exist_ok=True); a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if status!='PASS': a.output.unlink(missing_ok=True); return 2
    print('PASS_VALIDATED_CANDIDATE_MERGE'); print(result['output_sha256']); return 0
if __name__=='__main__': raise SystemExit(main())
