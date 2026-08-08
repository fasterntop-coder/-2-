#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

RAW=2352
USER_OFF=16
USER=2048
SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='daa1052fabd4142feaf42f14bdb5deefdf486cea8f0db8c939fc18ce6f822a56'
FINAL_SHA='dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83'
OLD_CHANGED=1901
NEW_ASSETS=30
NEW_FOOTPRINT=14767
NEW_CHANGED=13941
UNION_CHANGED=15842
EXPECTED_SOURCE_ECC_ANOMALIES=[250901]


def sha_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(8*1024*1024): h.update(chunk)
    return h.hexdigest()

def _edc_lut():
    out=[]
    for i in range(256):
        v=i
        for _ in range(8): v=(v>>1)^(0xD8018001 if v&1 else 0)
        out.append(v&0xffffffff)
    return out
EDC_LUT=_edc_lut()
def edc(data:bytes)->int:
    v=0
    for b in data: v=(v>>8)^EDC_LUT[(v^b)&255]
    return v&0xffffffff

def _ecc_luts():
    f=[0]*256;b=[0]*256
    for i in range(256):
        j=(i<<1)^(0x11D if i&0x80 else 0);f[i]=j&255;b[i^f[i]]=i
    return f,b
ECC_F,ECC_B=_ecc_luts()
def ecc(src:bytes,major_count:int,minor_count:int,major_mult:int,minor_inc:int)->bytes:
    size=major_count*minor_count;dest=bytearray(major_count*2)
    for major in range(major_count):
        index=(major>>1)*major_mult+(major&1);a=b=0
        for _ in range(minor_count):
            t=src[index];index+=minor_inc
            if index>=size:index-=size
            a^=t;b^=t;a=ECC_F[a]
        a=ECC_B[ECC_F[a]^b];dest[major]=a;dest[major+major_count]=a^b
    return bytes(dest)
def verify_mode1(sector:bytes)->dict[str,bool]:
    if len(sector)!=RAW:
        return {'size':False,'sync':False,'mode':False,'edc':False,'reserved':False,'ecc_p':False,'ecc_q':False,'valid':False}
    r={'size':True,'sync':sector[:12]==SYNC,'mode':sector[15]==1,
       'edc':int.from_bytes(sector[0x810:0x814],'little')==edc(sector[:0x810]),
       'reserved':sector[0x814:0x81c]==bytes(8),
       'ecc_p':sector[0x81c:0x8c8]==ecc(sector[0x0c:0x81c],86,24,2,86),
       'ecc_q':sector[0x8c8:0x930]==ecc(sector[0x0c:0x8c8],52,43,86,88)}
    r['valid']=all(r.values());return r
def rebuild_mode1(raw:bytes,user:bytes)->bytes:
    if len(raw)!=RAW or len(user)!=USER: raise ValueError('sector geometry')
    b=bytearray(raw);b[USER_OFF:USER_OFF+USER]=user
    b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little')
    b[0x814:0x81c]=bytes(8)
    b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86)
    b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88)
    out=bytes(b)
    if not verify_mode1(out)['valid']: raise ValueError('rebuilt MODE1 EDC/ECC failure')
    return out

def extract_user(disc:Path,lba:int,size:int)->bytes:
    out=bytearray();remain=size
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW);raw=f.read(RAW)
            if len(raw)!=RAW or raw[:12]!=SYNC or raw[15]!=1: raise ValueError(f'not MODE1/2352 at LBA {lba}')
            take=min(USER,remain);out+=raw[USER_OFF:USER_OFF+take];remain-=take;lba+=1
    return bytes(out)
def diff_lbas(left:Path,right:Path)->list[int]:
    result=[]
    with left.open('rb') as a,right.open('rb') as b:
        lba=0
        while True:
            x=a.read(RAW);y=b.read(RAW)
            if not x and not y:break
            if len(x)!=len(y):raise ValueError('disc size mismatch')
            if x!=y:result.append(lba)
            lba+=1
    return result

def load_assets(paths:list[Path])->list[dict]:
    assets=[]
    for p in paths:
        obj=json.loads(p.read_text(encoding='utf-8'))
        assets.extend(obj['replacement_files'])
    if len(assets)!=NEW_ASSETS: raise ValueError(f'expected {NEW_ASSETS} assets, got {len(assets)}')
    names=[Path(a['iso_path']).name for a in assets]
    if len(names)!=len(set(names)):raise ValueError('duplicate candidate filename')
    return assets

def main()->int:
    ap=argparse.ArgumentParser(description='Batch240 exact union: Batch239 parent + B51/B52/B64 promoted 30 assets')
    ap.add_argument('--pristine',type=Path,required=True)
    ap.add_argument('--parent',type=Path,required=True)
    ap.add_argument('--candidate-dir',type=Path,required=True)
    ap.add_argument('--patch-manifest',type=Path,action='append',required=True)
    ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B240_KO.bin'))
    ap.add_argument('--result',type=Path,default=Path('BATCH240_RESULT.json'))
    a=ap.parse_args()
    if sha_file(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine Disc SHA mismatch')
    if sha_file(a.parent)!=PARENT_SHA:raise SystemExit('Batch239 parent SHA mismatch')
    assets=load_assets(a.patch_manifest)
    footprint=set();per={};source_ecc_anomalies=[]
    for asset in assets:
        name=Path(asset['iso_path']).name;p=a.candidate_dir/name
        if not p.is_file() or p.stat().st_size!=asset['size'] or sha_file(p)!=asset['replacement_sha256']:
            raise SystemExit(f'candidate size/SHA mismatch: {name}')
        src=extract_user(a.pristine,asset['lba'],asset['size'])
        if sha_bytes(src)!=asset['source_sha256']:raise SystemExit(f'source asset SHA mismatch: {name}')
        ls=set(range(asset['lba'],asset['lba']+math.ceil(asset['size']/USER)))
        if footprint&ls:raise SystemExit(f'new asset overlap: {name}')
        footprint|=ls
        per[name]={'lba_first':asset['lba'],'lba_last':asset['lba']+len(ls)-1,'footprint_sectors':len(ls)}
    if len(footprint)!=NEW_FOOTPRINT:raise SystemExit(f'footprint count mismatch: {len(footprint)}')

    with a.pristine.open('rb') as src,a.parent.open('rb') as par:
        for lba in sorted(footprint):
            src.seek(lba*RAW);s=src.read(RAW);par.seek(lba*RAW);p=par.read(RAW)
            if s!=p:raise SystemExit(f'Batch239 parent overlaps new footprint at LBA {lba}')
            check=verify_mode1(s)
            if not check['valid']:
                if not (check['size'] and check['sync'] and check['mode'] and check['edc'] and check['reserved'] and check['ecc_p'] and not check['ecc_q']):
                    raise SystemExit(f'unexpected pristine sector defect at LBA {lba}: {check}')
                source_ecc_anomalies.append(lba)
    if source_ecc_anomalies!=EXPECTED_SOURCE_ECC_ANOMALIES:
        raise SystemExit(f'pristine ECC anomaly set mismatch: {source_ecc_anomalies}')
    old_changed=diff_lbas(a.pristine,a.parent)
    if len(old_changed)!=OLD_CHANGED or set(old_changed)&footprint:raise SystemExit('Batch239 changed-sector baseline/overlap mismatch')

    shutil.copyfile(a.parent,a.output)
    new_changed=[];expected_write=[]
    try:
        with a.pristine.open('rb') as src,a.parent.open('rb') as par,a.output.open('r+b') as dst:
            for asset in assets:
                name=Path(asset['iso_path']).name;cand=(a.candidate_dir/name).read_bytes();remain=asset['size'];pos=0;lba=asset['lba'];count=0
                while remain:
                    src.seek(lba*RAW);source_raw=src.read(RAW);par.seek(lba*RAW);parent_raw=par.read(RAW)
                    if source_raw!=parent_raw:raise ValueError(f'Expected Write parent mismatch LBA {lba}')
                    take=min(USER,remain);old_user=parent_raw[USER_OFF:USER_OFF+USER];new_user=bytearray(old_user);new_user[:take]=cand[pos:pos+take]
                    user_changed=bytes(new_user)!=old_user
                    if user_changed:
                        patched=rebuild_mode1(parent_raw,bytes(new_user));dst.seek(lba*RAW);dst.write(patched);new_changed.append(lba);count+=1
                    else:
                        patched=parent_raw
                    expected_write.append({'asset':name,'lba':lba,'source_sector_sha256':sha_bytes(source_raw),'patched_sector_sha256':sha_bytes(patched),'changed':user_changed})
                    remain-=take;pos+=take;lba+=1
                per[name]['changed_sectors']=count
        parent_delta=diff_lbas(a.parent,a.output)
        if len(parent_delta)!=NEW_CHANGED or set(parent_delta)!=set(new_changed):raise ValueError('new changed-sector accounting mismatch')
        if not set(new_changed)<=footprint:raise ValueError('change outside approved new footprint')
        with a.output.open('rb') as f:
            for lba in new_changed:
                f.seek(lba*RAW)
                if not verify_mode1(f.read(RAW))['valid']:raise ValueError(f'changed output EDC/ECC failure at LBA {lba}')
        union=diff_lbas(a.pristine,a.output)
        if len(union)!=UNION_CHANGED or set(union)!=(set(old_changed)|set(new_changed)):raise ValueError('union changed-sector accounting mismatch')
        for asset in assets:
            name=Path(asset['iso_path']).name
            if sha_bytes(extract_user(a.output,asset['lba'],asset['size']))!=asset['replacement_sha256']:
                raise ValueError(f'new asset re-extraction fail: {name}')
        final_sha=sha_file(a.output)
        if final_sha!=FINAL_SHA:raise ValueError(f'final Disc SHA mismatch: {final_sha}')
        result={'batch':240,'status':'PASS_BATCH239_PLUS_PROMOTED30_PHYSICAL_UNION',
                'parent_disc_sha256':PARENT_SHA,'output_disc_sha256':final_sha,
                'new_assets':30,'new_story_assets':27,'new_movie_assets':3,
                'previous_physical_assets':64,'total_physical_assets':94,
                'new_footprint_sectors':len(footprint),'new_changed_sectors':len(new_changed),
                'previous_changed_sectors':len(old_changed),'union_changed_sectors':len(union),
                'source_ecc_anomalies_preserved_when_user_data_unchanged':source_ecc_anomalies,
                'changed_sector_mode1_edc_ecc':f'{len(new_changed)}/{len(new_changed)} PASS',
                'new_reextraction':'30/30 PASS','parent_overlap':0,'outside_footprint_changes':0,
                'expected_write_records':len(expected_write),'per_asset':per,
                'safety':{'guessed_bytes':False,'source_raw_sha_expected_write':True,'unchanged_source_ecc_anomalies_not_repaired':True,'full_disc_distributed':False}}
        a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except Exception:
        a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
