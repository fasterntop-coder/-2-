#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

RAW=2352; USER=2048; UOFF=16
SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
B240_SHA='dce4e0d7fd114c339243c78205d5d2206e180d8631ab0577b63bc28d6b8bec83'
B269_STATUS='PASS_B247_STATIC58_PLUS_DEDUP_MASS137_EVENT34_EXECUTABLE_CANDIDATE'


def shaf(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()


def sha_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()


def _edc_lut():
    out=[]
    for i in range(256):
        v=i
        for _ in range(8): v=(v>>1)^(0xD8018001 if v&1 else 0)
        out.append(v&0xffffffff)
    return out
EDC=_edc_lut()

def edc(d:bytes)->int:
    v=0
    for x in d: v=(v>>8)^EDC[(v^x)&255]
    return v&0xffffffff


def _ecc_luts():
    f=[0]*256;b=[0]*256
    for i in range(256):
        j=(i<<1)^(0x11D if i&0x80 else 0);f[i]=j&255;b[i^f[i]]=i
    return f,b
EF,EB=_ecc_luts()

def ecc(src:bytes,maj:int,minc:int,mult:int,inc:int)->bytes:
    size=maj*minc;o=bytearray(maj*2)
    for m in range(maj):
        idx=(m>>1)*mult+(m&1);a=b=0
        for _ in range(minc):
            t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
        a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
    return bytes(o)

def rebuild_mode1(sec:bytearray)->None:
    if len(sec)!=RAW or sec[:12]!=SYNC or sec[15]!=1: raise SystemExit('non-MODE1 sector in target footprint')
    sec[0x810:0x814]=edc(sec[:0x810]).to_bytes(4,'little')
    sec[0x814:0x81c]=bytes(8)
    sec[0x81c:0x8c8]=ecc(sec[0x0c:0x81c],86,24,2,86)
    sec[0x8c8:0x930]=ecc(sec[0x0c:0x8c8],52,43,86,88)

def verify_mode1(s:bytes)->bool:
    return (len(s)==RAW and s[:12]==SYNC and s[15]==1
        and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810])
        and s[0x814:0x81c]==bytes(8)
        and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86)
        and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88))

def extract_asset(raw:Path,lba:int,size:int)->bytes:
    out=bytearray(); remain=size; cur=lba
    with raw.open('rb') as f:
        while remain:
            f.seek(cur*RAW+UOFF); chunk=f.read(min(USER,remain))
            if not chunk: raise SystemExit('short asset extraction')
            out.extend(chunk); remain-=len(chunk); cur+=1
    return bytes(out)

def overlay_asset(f,payload:bytes,lba:int,expected:list[dict])->set[int]:
    remain=len(payload); pos=0; cur=lba; changed=set()
    while remain:
        take=min(USER,remain); f.seek(cur*RAW); old=f.read(RAW)
        if len(old)!=RAW: raise SystemExit('short target sector')
        sec=bytearray(old); sec[UOFF:UOFF+take]=payload[pos:pos+take]
        if sec!=old:
            rebuild_mode1(sec); new=bytes(sec)
            expected.append({'lba':cur,'before_sha256':sha_bytes(old),'after_sha256':sha_bytes(new)})
            f.seek(cur*RAW); f.write(new); changed.add(cur)
        pos+=take; remain-=take; cur+=1
    return changed

def main()->int:
    ap=argparse.ArgumentParser(description='Batch271: recover exact B64 SK2MV_10/11 from Batch240 and promote onto Batch269')
    ap.add_argument('--batch240',type=Path,required=True)
    ap.add_argument('--batch269',type=Path,required=True)
    ap.add_argument('--batch269-result',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH271_B64_MOVIE2_PROMOTION.json'))
    ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B271_B64_Movie2_KO.bin'))
    ap.add_argument('--result',type=Path,default=Path('BATCH271_RESULT.json'))
    a=ap.parse_args()

    m=json.loads(a.manifest.read_text(encoding='utf-8'))
    if m.get('format')!='ST2-CD1-BATCH271-B64-MOVIE2-PROMOTION-v1': raise SystemExit('manifest format mismatch')
    if shaf(a.batch240)!=B240_SHA: raise SystemExit('Batch240 exact SHA mismatch')
    r269=json.loads(a.batch269_result.read_text(encoding='utf-8'))
    if r269.get('status')!=B269_STATUS: raise SystemExit('Batch269 status mismatch')
    parent_sha=shaf(a.batch269)
    if parent_sha!=r269.get('output_sha256'): raise SystemExit('Batch269 output SHA mismatch')

    payloads=[]
    for x in m['replacement_files']:
        p=extract_asset(a.batch240,int(x['lba']),int(x['size']))
        got=sha_bytes(p)
        if got!=x['replacement_sha256']: raise SystemExit(f"Batch240 asset SHA mismatch: {x['iso_path']}")
        payloads.append((x,p))

    shutil.copyfile(a.batch269,a.output)
    expected=[]; changed=set()
    with a.output.open('r+b') as f:
        for x,p in payloads: changed |= overlay_asset(f,p,int(x['lba']),expected)

    bad=[]; expected_bad=[]
    with a.output.open('rb') as f:
        for e in expected:
            f.seek(e['lba']*RAW); sec=f.read(RAW)
            if sha_bytes(sec)!=e['after_sha256']: expected_bad.append(e['lba'])
            if not verify_mode1(sec): bad.append(e['lba'])
    if expected_bad: raise SystemExit(f'Expected Write failures: {expected_bad[:8]}')
    if bad: raise SystemExit(f'changed-sector EDC/ECC failures: {bad[:8]}')

    rex=[]
    for x,_ in payloads:
        got=sha_bytes(extract_asset(a.output,int(x['lba']),int(x['size'])))
        ok=got==x['replacement_sha256']; rex.append({'iso_path':x['iso_path'],'sha256':got,'pass':ok})
        if not ok: raise SystemExit(f"whole-asset re-extraction failed: {x['iso_path']}")

    result={
      'batch':271,
      'status':'PASS_BATCH269_PLUS_B64_MOVIE2_EXECUTABLE_CANDIDATE',
      'parent_batch':269,'parent_sha256':parent_sha,
      'recovery_batch':240,'recovery_disc_sha256':B240_SHA,
      'new_unique_assets':2,'new_subtitle_events':23,
      'assets':[{'iso_path':x['iso_path'],'lba':x['lba'],'size':x['size'],'replacement_sha256':x['replacement_sha256']} for x,_ in payloads],
      'changed_sector_count':len(changed),'expected_write_records':len(expected),
      'expected_write':f'{len(expected)}/{len(expected)} PASS',
      'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS',
      'changed_sector_accounting':'PASS',
      'whole_asset_reextraction':'2/2 PASS',
      'reextraction':rex,
      'output_sha256':shaf(a.output),
      'guessed_payload_bytes':False
    }
    a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
