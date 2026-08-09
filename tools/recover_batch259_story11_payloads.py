#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile, zipfile
from pathlib import Path

RAW=2352; USER_OFF=16; USER=2048; DISC_SIZE=659293824
MANIFEST=Path('manifests/CD1_BATCH259_STORY11_MEGA_PROMOTION.json')

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024):h.update(c)
    return h.hexdigest()

def extract_raw(disc:Path,lba:int,size:int)->bytes:
    out=bytearray();remain=size
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW);s=f.read(RAW)
            if len(s)!=RAW or s[:12] != bytes([0]+[0xff]*10+[0]) or s[15]!=1:
                raise ValueError(f'not MODE1/2352 at LBA {lba}')
            n=min(USER,remain);out+=s[USER_OFF:USER_OFF+n];remain-=n;lba+=1
    return bytes(out)

def main()->int:
    ap=argparse.ArgumentParser(description='Batch259 exact recovery for 11 high-value Disc1 story banks')
    ap.add_argument('--root',type=Path,action='append',required=True)
    ap.add_argument('--include-zip',action='store_true')
    ap.add_argument('--manifest',type=Path,default=MANIFEST)
    ap.add_argument('--output-dir',type=Path,default=Path('BATCH259_STORY11_CANDIDATES'))
    ap.add_argument('--result',type=Path,default=Path('BATCH259_RECOVERY_RESULT.json'))
    a=ap.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8'));xs=m['replacement_files']
    if m.get('format')!='ST2-CD1-BATCH259-STORY11-MEGA-PROMOTION-v1' or len(xs)!=11:raise SystemExit('manifest/cardinality mismatch')
    a.output_dir.mkdir(parents=True,exist_ok=True)
    by_hash={x['replacement_sha256']:x for x in xs};by_size={}
    for x in xs:by_size.setdefault(x['size'],[]).append(x)
    found={};scanned={'loose':0,'raw_disc':0,'zip':0,'zip_disc':0}
    def accept(data:bytes,src:str):
        h=shab(data);x=by_hash.get(h)
        if not x or len(data)!=x['size'] or x['iso_path'] in found:return False
        p=a.output_dir/Path(x['iso_path']).name;p.write_bytes(data)
        if shaf(p)!=x['replacement_sha256']:p.unlink(missing_ok=True);raise ValueError('post-write SHA mismatch')
        found[x['iso_path']]={'path':str(p),'sha256':h,'source':src};return True
    for root in a.root:
        if not root.exists():continue
        items=[root] if root.is_file() else root.rglob('*')
        for p in items:
            if not p.is_file():continue
            try:
                sz=p.stat().st_size
                if sz in by_size:
                    scanned['loose']+=1;accept(p.read_bytes(),str(p))
                elif sz==DISC_SIZE:
                    scanned['raw_disc']+=1
                    for x in xs:accept(extract_raw(p,x['lba'],x['size']),f'{p}@LBA{x["lba"]}')
                elif a.include_zip and p.suffix.lower()=='.zip':
                    scanned['zip']+=1
                    with zipfile.ZipFile(p) as z:
                        for zi in z.infolist():
                            if zi.file_size in by_size:accept(z.read(zi),f'{p}!{zi.filename}')
                            elif zi.file_size==DISC_SIZE:
                                scanned['zip_disc']+=1
                                with tempfile.TemporaryDirectory() as td:
                                    q=Path(td)/'disc.bin'
                                    with z.open(zi) as src,q.open('wb') as dst:shutil.copyfileobj(src,dst,8*1024*1024)
                                    for x in xs:accept(extract_raw(q,x['lba'],x['size']),f'{p}!{zi.filename}@LBA{x["lba"]}')
            except (OSError,ValueError,zipfile.BadZipFile):
                continue
    missing=[x['iso_path'] for x in xs if x['iso_path'] not in found]
    result={'batch':259,'status':'PASS_STORY11_EXACT_RECOVERY_SCAN_COMPLETE' if not missing else 'PARTIAL_EXACT_RECOVERY','required':11,'recovered':len(found),'missing':missing,'found':found,'scanned':scanned,'guessed_bytes':False,'ready_for_physical_promotion':not missing}
    a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
