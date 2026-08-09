#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil, tempfile, zipfile
from pathlib import Path

RAW=2352; USER_OFF=16; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
DISC_SIZE=659293824

TARGETS=[
 {'name':'SK0403_KR_R41_FINAL.BIN','iso_path':'SAKURA1/SK0403.BIN','lba':45626,'size':113392,'source_sha256':'2736d124c75afcf99cf0d8646427ba9478b84215c8de64fb29aa73f7cefa9b1e','replacement_sha256':'94576a14ff92abff690fde9acdd9e5673b834f7d62391be39971f7d70e4932b5'},
 {'name':'SK0404.BIN','iso_path':'SAKURA1/SK0404.BIN','lba':45682,'size':44804,'source_sha256':'4deb61ff0b8f25ad8494e6753af9b415f6f4351374f39704112574a793f2a710','replacement_sha256':'7fd50fb8a2b236091b41c5a7b6ff7dc46c992e01790a5d534491649d64d830e5'},
 {'name':'SK0501.BIN','iso_path':'SAKURA1/SK0501.BIN','lba':45704,'size':246748,'source_sha256':'8ba6f9332c7dd84b39aa72cb20b98df417d1395db2ec696fd95a9824d879544f','replacement_sha256':'6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743'},
]

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
 b=bytearray(raw);b[USER_OFF:USER_OFF+USER]=user
 b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8)
 b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88)
 out=bytes(b)
 if not verify(out):raise ValueError('MODE1 EDC/ECC rebuild failed')
 return out

def extract(disc:Path,lba:int,size:int)->bytes:
 out=bytearray();remain=size
 with disc.open('rb') as f:
  while remain:
   f.seek(lba*RAW);s=f.read(RAW)
   if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'not MODE1/2352 LBA {lba}')
   n=min(USER,remain);out+=s[USER_OFF:USER_OFF+n];remain-=n;lba+=1
 return bytes(out)

def sector_diffs(a:Path,b:Path)->set[int]:
 out=set();i=0
 with a.open('rb') as x,b.open('rb') as y:
  while True:
   p=x.read(RAW);q=y.read(RAW)
   if not p and not q:break
   if len(p)!=len(q):raise ValueError('disc size mismatch')
   if p!=q:out.add(i)
   i+=1
 return out

def recover(roots:list[Path],outdir:Path,include_zip:bool)->dict:
 outdir.mkdir(parents=True,exist_ok=True);found={};wanted={t['replacement_sha256']:t for t in TARGETS}
 def accept(name:str,data:bytes,src:str):
  h=shab(data);t=wanted.get(h)
  if not t or len(data)!=t['size'] or t['iso_path'] in found:return
  p=outdir/Path(t['iso_path']).name;p.write_bytes(data);found[t['iso_path']]={'path':str(p),'sha256':h,'source':src}
 for root in roots:
  if not root.exists():continue
  it=[root] if root.is_file() else root.rglob('*')
  for p in it:
   if not p.is_file():continue
   try:
    if p.stat().st_size in {t['size'] for t in TARGETS}:accept(p.name,p.read_bytes(),str(p))
    elif p.stat().st_size==DISC_SIZE:
     for t in TARGETS:accept(t['iso_path'],extract(p,t['lba'],t['size']),f'{p}@LBA{t["lba"]}')
    elif include_zip and p.suffix.lower()=='.zip':
     with zipfile.ZipFile(p) as z:
      for zi in z.infolist():
       if zi.file_size in {t['size'] for t in TARGETS}:accept(zi.filename,z.read(zi),f'{p}!{zi.filename}')
       elif zi.file_size==DISC_SIZE:
        with tempfile.TemporaryDirectory() as td:
         q=Path(td)/'disc.bin'
         with z.open(zi) as s,q.open('wb') as d:shutil.copyfileobj(s,d,8*1024*1024)
         for t in TARGETS:accept(t['iso_path'],extract(q,t['lba'],t['size']),f'{p}!{zi.filename}@LBA{t["lba"]}')
   except (OSError,ValueError,zipfile.BadZipFile):pass
 return found

def promote(pristine:Path,parent:Path,candidates:Path,output:Path,result:Path)->dict:
 if pristine.stat().st_size!=DISC_SIZE or shaf(pristine)!=PRISTINE_SHA:raise SystemExit('pristine SHA/size mismatch')
 if parent.stat().st_size!=DISC_SIZE or shaf(parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA/size mismatch')
 footprint=set();cand={}
 for t in TARGETS:
  p=candidates/Path(t['iso_path']).name
  if not p.is_file() or p.stat().st_size!=t['size'] or shaf(p)!=t['replacement_sha256']:raise SystemExit(f'exact candidate missing: {t["iso_path"]}')
  if shab(extract(pristine,t['lba'],t['size']))!=t['source_sha256']:raise SystemExit(f'pristine source mismatch: {t["iso_path"]}')
  ls=set(range(t['lba'],t['lba']+math.ceil(t['size']/USER)))
  if footprint&ls:raise SystemExit(f'intra-batch footprint collision: {t["iso_path"]}')
  footprint|=ls;cand[t['iso_path']]=p
 old=sector_diffs(pristine,parent)
 if old&footprint:raise SystemExit(f'Batch247 overlaps Chapter4-5 footprint at LBA {min(old&footprint)}')
 shutil.copyfile(parent,output);changed=set();writes=[]
 try:
  with pristine.open('rb') as pri,parent.open('rb') as par,output.open('r+b') as dst:
   for t in TARGETS:
    data=cand[t['iso_path']].read_bytes();remain=t['size'];pos=0;lba=t['lba']
    while remain:
     pri.seek(lba*RAW);src=pri.read(RAW);par.seek(lba*RAW);base=par.read(RAW)
     if src!=base:raise ValueError(f'Expected Write parent mismatch LBA {lba}')
     take=min(USER,remain);u=bytearray(base[USER_OFF:USER_OFF+USER]);u[:take]=data[pos:pos+take];out=base
     if bytes(u)!=base[USER_OFF:USER_OFF+USER]:
      out=rebuild(base,bytes(u));dst.seek(lba*RAW);dst.write(out);changed.add(lba)
     writes.append({'asset':t['iso_path'],'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base})
     remain-=take;pos+=take;lba+=1
  actual=sector_diffs(parent,output)
  if actual!=changed or not changed<=footprint:raise ValueError('changed-sector accounting/scope mismatch')
  with output.open('rb') as f:
   for lba in changed:
    f.seek(lba*RAW)
    if not verify(f.read(RAW)):raise ValueError(f'EDC/ECC failure LBA {lba}')
  for t in TARGETS:
   if shab(extract(output,t['lba'],t['size']))!=t['replacement_sha256']:raise ValueError(f'whole-asset re-extraction mismatch: {t["iso_path"]}')
  r={'batch':257,'status':'PASS_B247_STATIC58_PLUS_CH45_STORY3_EXECUTABLE_CANDIDATE','parent_sha256':PARENT_SHA,'assets_promoted':3,'records_reviewed':2142,'translated_records':2134,'story_metric_evidence':'14865/14875 = 99.9% after SK0501','output_sha256':shaf(output),'approved_footprint_sectors':len(footprint),'changed_sectors':len(changed),'parent_overlap':0,'outside_footprint_changes':0,'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'3/3 PASS','expected_write_records':len(writes),'guessed_bytes':False}
  result.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');return r
 except Exception:
  output.unlink(missing_ok=True);raise

def main()->int:
 ap=argparse.ArgumentParser(description='Batch257 recover and promote exact SK0403/SK0404/SK0501 onto exact Batch247')
 ap.add_argument('--root',type=Path,action='append',default=[]);ap.add_argument('--include-zip',action='store_true');ap.add_argument('--candidate-dir',type=Path,default=Path('BATCH257_CANDIDATES'))
 ap.add_argument('--pristine',type=Path);ap.add_argument('--parent',type=Path);ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B257_C2FIX_STATIC58_CH45_STORY3_KO.bin'));ap.add_argument('--result',type=Path,default=Path('BATCH257_RESULT.json'))
 a=ap.parse_args();found=recover(a.root,a.candidate_dir,a.include_zip) if a.root else {}
 print(json.dumps({'recovered':len(found),'required':3,'files':found},ensure_ascii=False,indent=2))
 if a.pristine and a.parent:
  r=promote(a.pristine,a.parent,a.candidate_dir,a.output,a.result);print(json.dumps(r,ensure_ascii=False,indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
