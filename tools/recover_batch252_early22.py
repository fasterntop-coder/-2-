#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

RAW=2352
USER_OFF=16
USER=2048
SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
R36_SHA='ef41d60d64e05479c2ca8cb255f29080909b3584c615983b30edaec4d8f4a605'


def shab(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def shaf(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()

def extract(disc:Path,lba:int,size:int)->bytes:
    out=bytearray(); remain=size
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW); s=f.read(RAW)
            if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:
                raise ValueError(f'not MODE1/2352 at LBA {lba}')
            n=min(USER,remain); out+=s[USER_OFF:USER_OFF+n]
            remain-=n; lba+=1
    return bytes(out)

def main()->int:
    ap=argparse.ArgumentParser(description='Recover exact early 22 story payloads for Batch252/Story109')
    ap.add_argument('--pristine',type=Path,required=True)
    ap.add_argument('--st2r36',type=Path,required=True)
    ap.add_argument('--batch46-dir',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH252_EARLY22_EXACT_RECOVERY.json'))
    ap.add_argument('--output-dir',type=Path,default=Path('BATCH252_EARLY22_PAYLOADS'))
    ap.add_argument('--result',type=Path,default=Path('BATCH252_EARLY22_RESULT.json'))
    a=ap.parse_args()

    m=json.loads(a.manifest.read_text(encoding='utf-8'))
    xs=m.get('assets',[])
    if m.get('format')!='ST2-CD1-BATCH252-EARLY22-EXACT-RECOVERY-v1' or len(xs)!=22:
        raise SystemExit('manifest format/cardinality mismatch')
    if shaf(a.pristine)!=PRISTINE_SHA:
        raise SystemExit('pristine Disc 1 SHA mismatch')
    if shaf(a.st2r36)!=R36_SHA:
        raise SystemExit('historical ST2R36 SHA mismatch')

    tmp=a.output_dir.with_name(a.output_dir.name+'.tmp')
    shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True)
    per=[]
    try:
        for x in xs:
            n=Path(x['iso_path']).name
            src=extract(a.pristine,x['lba'],x['size'])
            if shab(src)!=x['source_sha256']:
                raise ValueError(f'pristine source SHA mismatch: {n}')
            if x['recovery']=='ST2R36':
                payload=extract(a.st2r36,x['lba'],x['size'])
                provenance='exact ST2R36 full-disc SHA + raw-sector extraction'
            elif x['recovery']=='BATCH46_LOOSE':
                p=a.batch46_dir/n
                if not p.is_file() or p.stat().st_size!=x['size']:
                    raise ValueError(f'missing/size mismatch Batch46 payload: {n}')
                payload=p.read_bytes(); provenance='exact Batch46 loose payload SHA'
            else:
                raise ValueError(f'unknown recovery mode: {n}')
            got=shab(payload)
            if got!=x['replacement_sha256']:
                raise ValueError(f'replacement SHA mismatch: {n}: {got}')
            (tmp/n).write_bytes(payload)
            per.append({'asset':n,'lba':x['lba'],'size':x['size'],'source_sha256':x['source_sha256'],'replacement_sha256':got,'recovery':x['recovery'],'provenance':provenance,'status':'PASS'})
        if a.output_dir.exists(): shutil.rmtree(a.output_dir)
        tmp.rename(a.output_dir)
        r={'batch':252,'status':'PASS_EARLY22_EXACT_PAYLOADS_RECOVERED','asset_count':22,'st2r36_recovered':19,'batch46_verified':3,'guessed_bytes':False,'pristine_disc_sha256':PRISTINE_SHA,'historical_st2r36_disc_sha256':R36_SHA,'output_dir':str(a.output_dir),'assets':per}
        a.result.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(r,ensure_ascii=False,indent=2)); return 0
    except Exception:
        shutil.rmtree(tmp,ignore_errors=True); raise

if __name__=='__main__':
    raise SystemExit(main())
