#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil
from pathlib import Path
RAW=2352; USER_OFF=16; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
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
EDC=_edc_lut()
def edc(d:bytes)->int:
 v=0
 for x in d:v=(v>>8)^EDC[(v^x)&255]
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
   t=src[idx];idx+=inc
   if idx>=size:idx-=size
   a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
 return bytes(o)
def verify(s:bytes)->bool:
 return len(s)==RAW and s[:12]==SYNC and s[15]==1 and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and s[0x814:0x81c]==bytes(8) and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88)
def rebuild(raw:bytes,user:bytes)->bytes:
 b=bytearray(raw);b[USER_OFF:USER_OFF+USER]=user;b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8);b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88);o=bytes(b)
 if not verify(o):raise ValueError('MODE1 EDC/ECC rebuild failed')
 return o
def extract(disc:Path,lba:int,size:int)->bytes:
 o=bytearray();r=size
 with disc.open('rb') as f:
  while r:
   f.seek(lba*RAW);s=f.read(RAW)
   if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'not MODE1/2352 LBA {lba}')
   n=min(USER,r);o+=s[USER_OFF:USER_OFF+n];r-=n;lba+=1
 return bytes(o)
def diffs(a:Path,b:Path)->set[int]:
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
 ap=argparse.ArgumentParser(description='Batch253 exact Story109 physical promotion onto verified Batch247')
 ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--candidate-dir',type=Path,required=True)
 ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'));ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B253_C2FIX_STATIC58_STORY109_KO.bin'));ap.add_argument('--result',type=Path,default=Path('BATCH253_RESULT.json'))
 a=ap.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8'));xs=m.get('replacement_files',[]);controls=m.get('control_files',[])
 if m.get('format')!='ST2-CD1-BATCH253-STORY109-PROMOTION-v1' or m.get('replacement_asset_count')!=107 or len(xs)!=107 or len(controls)!=2:raise SystemExit('manifest format/cardinality mismatch')
 if m.get('physical_parent_disc_sha256')!=PARENT_SHA or shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA mismatch')
 if m.get('pristine_disc_sha256')!=PRISTINE_SHA or shaf(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine SHA mismatch')
 footprint=set();control_footprint=set();per={}
 for x in xs:
  n=Path(x['iso_path']).name;p=a.candidate_dir/n
  if not p.is_file() or p.stat().st_size!=x['size'] or shaf(p)!=x['replacement_sha256']:raise SystemExit(f'candidate exact gate failed: {n}')
  if shab(extract(a.pristine,x['lba'],x['size']))!=x['source_sha256']:raise SystemExit(f'pristine source SHA failed: {n}')
  ls=set(range(x['lba'],x['lba']+math.ceil(x['size']/USER)))
  if footprint&ls:raise SystemExit(f'replacement footprint collision: {n}')
  footprint|=ls;per[n]={'lba':x['lba'],'size':x['size'],'footprint_sectors':len(ls)}
 for c in controls:
  n=Path(c['iso_path']).name
  if shab(extract(a.pristine,c['lba'],c['size']))!=c['source_sha256']:raise SystemExit(f'pristine control SHA failed: {n}')
  if shab(extract(a.parent,c['lba'],c['size']))!=c['source_sha256']:raise SystemExit(f'parent control not pristine: {n}')
  ls=set(range(c['lba'],c['lba']+math.ceil(c['size']/USER)))
  if footprint&ls or control_footprint&ls:raise SystemExit(f'control footprint collision: {n}')
  control_footprint|=ls
 old=diffs(a.pristine,a.parent)
 if old&footprint:raise SystemExit(f'Batch247 overlaps replacement footprint at LBA {min(old&footprint)}')
 if old&control_footprint:raise SystemExit(f'Batch247 overlaps control footprint at LBA {min(old&control_footprint)}')
 shutil.copyfile(a.parent,a.output);changed=set();expected=[]
 try:
  with a.pristine.open('rb') as pri,a.parent.open('rb') as par,a.output.open('r+b') as dst:
   for x in xs:
    n=Path(x['iso_path']).name;c=(a.candidate_dir/n).read_bytes();r=x['size'];pos=0;lba=x['lba'];cnt=0
    while r:
     pri.seek(lba*RAW);src=pri.read(RAW);par.seek(lba*RAW);base=par.read(RAW)
     if src!=base:raise ValueError(f'Expected Write parent mismatch LBA {lba}')
     take=min(USER,r);u=bytearray(base[USER_OFF:USER_OFF+USER]);u[:take]=c[pos:pos+take];out=base
     if bytes(u)!=base[USER_OFF:USER_OFF+USER]:out=rebuild(base,bytes(u));dst.seek(lba*RAW);dst.write(out);changed.add(lba);cnt+=1
     expected.append({'asset':n,'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base})
     r-=take;pos+=take;lba+=1
    per[n]['changed_sectors']=cnt
  actual=diffs(a.parent,a.output)
  if actual!=changed:raise ValueError('changed-sector accounting mismatch')
  if not changed<=footprint:raise ValueError('change outside approved replacement footprint')
  if changed&control_footprint:raise ValueError('control sector changed')
  with a.output.open('rb') as f:
   for lba in changed:
    f.seek(lba*RAW)
    if not verify(f.read(RAW)):raise ValueError(f'EDC/ECC failure LBA {lba}')
  for x in xs:
   n=Path(x['iso_path']).name
   if shab(extract(a.output,x['lba'],x['size']))!=x['replacement_sha256']:raise ValueError(f'whole-asset re-extraction mismatch: {n}')
  for c in controls:
   n=Path(c['iso_path']).name
   if shab(extract(a.output,c['lba'],c['size']))!=c['source_sha256']:raise ValueError(f'control re-extraction mismatch: {n}')
  result={'batch':253,'status':'PASS_B247_STATIC58_PLUS_STORY109_EXECUTABLE_CANDIDATE','parent_batch':247,'parent_sha256':PARENT_SHA,'story_replacement_assets_promoted':107,'story_control_assets_preserved':2,'story_files_accounted':109,'output_sha256':shaf(a.output),'approved_replacement_footprint_sectors':len(footprint),'control_footprint_sectors':len(control_footprint),'changed_sectors':len(changed),'parent_overlap':0,'outside_footprint_changes':0,'control_sector_changes':0,'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'107/107 PASS','control_reextraction':'2/2 PASS','expected_write_records':len(expected),'safety':{'guessed_bytes':False,'exact_candidate_sha256':True,'exact_pristine_source_sha256':True,'expected_write':True,'changed_sector_accounting':True,'controls_pristine':True},'per_asset':per}
  a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except Exception:
  a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
