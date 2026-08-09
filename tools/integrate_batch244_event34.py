#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil
from pathlib import Path
RAW=2352; USER_OFF=16; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83'

def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024):h.update(c)
    return h.hexdigest()
def _edc_lut():
    out=[]
    for i in range(256):
        v=i
        for _ in range(8):v=(v>>1)^(0xD8018001 if v&1 else 0)
        out.append(v&0xffffffff)
    return out
EDC_LUT=_edc_lut()
def edc(data:bytes)->int:
    v=0
    for x in data:v=(v>>8)^EDC_LUT[(v^x)&255]
    return v&0xffffffff
def _ecc_luts():
    f=[0]*256;b=[0]*256
    for i in range(256):
        j=(i<<1)^(0x11D if i&0x80 else 0);f[i]=j&255;b[i^f[i]]=i
    return f,b
ECC_F,ECC_B=_ecc_luts()
def ecc(src:bytes,maj:int,minc:int,mult:int,inc:int)->bytes:
    size=maj*minc;d=bytearray(maj*2)
    for m in range(maj):
        idx=(m>>1)*mult+(m&1);a=b=0
        for _ in range(minc):
            t=src[idx];idx+=inc
            if idx>=size:idx-=size
            a^=t;b^=t;a=ECC_F[a]
        a=ECC_B[ECC_F[a]^b];d[m]=a;d[m+maj]=a^b
    return bytes(d)
def verify_mode1(s:bytes)->bool:
    return len(s)==RAW and s[:12]==SYNC and s[15]==1 and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and s[0x814:0x81c]==bytes(8) and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88)
def rebuild(raw:bytes,user:bytes)->bytes:
    b=bytearray(raw);b[USER_OFF:USER_OFF+USER]=user;b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8);b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88);o=bytes(b)
    if not verify_mode1(o):raise ValueError('EDC/ECC rebuild failure')
    return o
def extract(disc:Path,lba:int,size:int)->bytes:
    out=bytearray();remain=size
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW);s=f.read(RAW)
            if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'not MODE1/2352 LBA {lba}')
            take=min(USER,remain);out+=s[USER_OFF:USER_OFF+take];remain-=take;lba+=1
    return bytes(out)
def diff_lbas(a:Path,b:Path)->set[int]:
    out=set();i=0
    with a.open('rb') as x,b.open('rb') as y:
        while True:
            p=x.read(RAW);q=y.read(RAW)
            if not p and not q:break
            if len(p)!=len(q):raise ValueError('disc size mismatch')
            if p!=q:out.add(i)
            i+=1
    return out

def main()->int:
    ap=argparse.ArgumentParser(description='Batch244: promote exact B53+B55 34 event MES onto Batch240 parent')
    ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--candidate-dir',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH244_EVENT34_PROMOTION.json'));ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B244_KO.bin'));ap.add_argument('--result',type=Path,default=Path('BATCH244_RESULT.json'))
    a=ap.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8'));assets=m['replacement_files']
    if m.get('format')!='ST2-CD1-BATCH244-EVENT34-PROMOTION-v1' or len(assets)!=34:raise SystemExit('manifest format/cardinality mismatch')
    if sha_file(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine SHA mismatch')
    if sha_file(a.parent)!=PARENT_SHA:raise SystemExit('Batch240 parent SHA mismatch')
    names=[Path(x['iso_path']).name for x in assets]
    if len(set(names))!=34:raise SystemExit('duplicate asset name')
    footprint=set();per={}
    for x in assets:
        n=Path(x['iso_path']).name;p=a.candidate_dir/n
        if not p.is_file() or p.stat().st_size!=x['size'] or sha_file(p)!=x['replacement_sha256']:raise SystemExit(f'candidate size/SHA mismatch: {n}')
        if sha_bytes(extract(a.pristine,x['lba'],x['size']))!=x['source_sha256']:raise SystemExit(f'pristine source SHA mismatch: {n}')
        ls=set(range(x['lba'],x['lba']+math.ceil(x['size']/USER)))
        if footprint&ls:raise SystemExit(f'candidate footprint collision: {n}')
        footprint|=ls;per[n]={'footprint_sectors':len(ls),'lba_first':min(ls),'lba_last':max(ls)}
    old=diff_lbas(a.pristine,a.parent)
    if old&footprint:raise SystemExit(f'Batch240 overlap with Event34 footprint at {min(old&footprint)}')
    shutil.copyfile(a.parent,a.output);changed=set();writes=[]
    try:
        with a.pristine.open('rb') as pri,a.parent.open('rb') as par,a.output.open('r+b') as dst:
            for x in assets:
                n=Path(x['iso_path']).name;c=(a.candidate_dir/n).read_bytes();remain=x['size'];pos=0;lba=x['lba'];cnt=0
                while remain:
                    pri.seek(lba*RAW);s=pri.read(RAW);par.seek(lba*RAW);p=par.read(RAW)
                    if s!=p:raise ValueError(f'Expected Write parent mismatch LBA {lba}')
                    take=min(USER,remain);u=bytearray(p[USER_OFF:USER_OFF+USER]);u[:take]=c[pos:pos+take]
                    out=p
                    if bytes(u)!=p[USER_OFF:USER_OFF+USER]:out=rebuild(p,bytes(u));dst.seek(lba*RAW);dst.write(out);changed.add(lba);cnt+=1
                    writes.append({'asset':n,'lba':lba,'expected_parent_sha256':sha_bytes(p),'written_sha256':sha_bytes(out),'changed':out!=p})
                    remain-=take;pos+=take;lba+=1
                per[n]['changed_sectors']=cnt
        actual=diff_lbas(a.parent,a.output)
        if actual!=changed:raise ValueError('changed-sector accounting mismatch')
        if not changed<=footprint:raise ValueError('change outside approved footprint')
        with a.output.open('rb') as f:
            for lba in changed:
                f.seek(lba*RAW)
                if not verify_mode1(f.read(RAW)):raise ValueError(f'EDC/ECC failure LBA {lba}')
        for x in assets:
            n=Path(x['iso_path']).name
            if sha_bytes(extract(a.output,x['lba'],x['size']))!=x['replacement_sha256']:raise ValueError(f're-extraction mismatch: {n}')
        result={'batch':244,'status':'PASS_EVENT34_PHYSICAL_PROMOTION','parent_sha256':PARENT_SHA,'output_sha256':sha_file(a.output),'assets_promoted':34,'previous_physical_assets':94,'total_physical_assets':128,'footprint_sectors':len(footprint),'changed_sectors':len(changed),'parent_overlap':0,'outside_footprint_changes':0,'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'34/34 PASS','expected_write_records':len(writes),'per_asset':per,'safety':{'guessed_bytes':False,'exact_candidate_sha256':True,'exact_pristine_source_sha256':True}}
        a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except Exception:
        a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
