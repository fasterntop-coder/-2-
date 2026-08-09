#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil, zipfile
from pathlib import Path

RAW=2352; USER_OFF=16; USER=2048; DISC_SIZE=659293824
SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
B247_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
R40C_SHA='0a8ef45602cec5515e29367601b43951229a402321fd7862dd54a970c01a3dcb'
ASSET='SK0401.BIN'; LBA=45453; SIZE=104080
SOURCE_SHA='2f9a8d68405b330103dfe517fbcf8af6615cab2ddb2554d29d59fc155194b786'

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
 o=bytes(b)
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

def locate_r40c(roots:list[Path],tmp:Path)->tuple[Path,str]:
 for root in roots:
  if not root.exists():continue
  for p in root.rglob('*.bin'):
   if p.stat().st_size==DISC_SIZE and shaf(p)==R40C_SHA:return p,'loose_bin'
  for z in root.rglob('*.zip'):
   try:
    with zipfile.ZipFile(z) as q:
     for info in q.infolist():
      if info.file_size!=DISC_SIZE or not info.filename.lower().endswith('.bin'):continue
      tmp.mkdir(parents=True,exist_ok=True);dst=tmp/'R40C_RECOVERED.bin'
      h=hashlib.sha256()
      with q.open(info) as src,dst.open('wb') as out:
       while c:=src.read(8*1024*1024):h.update(c);out.write(c)
      if h.hexdigest()==R40C_SHA:return dst,f'zip:{z.name}:{info.filename}'
      dst.unlink(missing_ok=True)
   except (zipfile.BadZipFile,OSError):pass
 raise FileNotFoundError('exact R40C full-disc SHA not found')

def main()->int:
 ap=argparse.ArgumentParser(description='Batch260 exact SK0401 recovery from verified R40C and promotion onto Batch247')
 ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True)
 ap.add_argument('--root',type=Path,action='append',required=True);ap.add_argument('--work',type=Path,default=Path('BATCH260_WORK'))
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B260_B247_SK0401_KO.bin'))
 ap.add_argument('--result',type=Path,default=Path('BATCH260_RESULT.json'))
 a=ap.parse_args()
 if a.pristine.stat().st_size!=DISC_SIZE or shaf(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine Disc1 gate failed')
 if a.parent.stat().st_size!=DISC_SIZE or shaf(a.parent)!=B247_SHA:raise SystemExit('Batch247 parent gate failed')
 r40c,provenance=locate_r40c(a.root,a.work/'tmp')
 payload=extract(r40c,LBA,SIZE);replacement_sha=shab(payload)
 if shab(extract(a.pristine,LBA,SIZE))!=SOURCE_SHA:raise SystemExit('SK0401 pristine source SHA mismatch')
 footprint=set(range(LBA,LBA+math.ceil(SIZE/USER)));old=diffs(a.pristine,a.parent)
 if old&footprint:raise SystemExit(f'Batch247 overlaps SK0401 footprint at LBA {min(old&footprint)}')
 a.work.mkdir(parents=True,exist_ok=True);(a.work/ASSET).write_bytes(payload)
 shutil.copyfile(a.parent,a.output);changed=set();expected=[]
 with a.pristine.open('rb') as pri,a.parent.open('rb') as par,a.output.open('r+b') as dst:
  r=SIZE;pos=0;lba=LBA
  while r:
   pri.seek(lba*RAW);src=pri.read(RAW);par.seek(lba*RAW);base=par.read(RAW)
   if src!=base:raise ValueError(f'Expected Write parent mismatch LBA {lba}')
   take=min(USER,r);u=bytearray(base[USER_OFF:USER_OFF+USER]);u[:take]=payload[pos:pos+take]
   out=base
   if bytes(u)!=base[USER_OFF:USER_OFF+USER]:out=rebuild(base,bytes(u));dst.seek(lba*RAW);dst.write(out);changed.add(lba)
   expected.append({'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base})
   r-=take;pos+=take;lba+=1
 actual=diffs(a.parent,a.output)
 if actual!=changed or not changed<=footprint:raise ValueError('changed-sector accounting mismatch')
 with a.output.open('rb') as f:
  for lba in changed:
   f.seek(lba*RAW)
   if not verify(f.read(RAW)):raise ValueError(f'EDC/ECC failure LBA {lba}')
 if shab(extract(a.output,LBA,SIZE))!=replacement_sha:raise ValueError('whole-asset re-extraction mismatch')
 result={'batch':260,'status':'PASS_EXACT_R40C_SK0401_PROMOTED_ONTO_B247','r40c_disc_sha256':R40C_SHA,'r40c_provenance':provenance,'asset':ASSET,'lba':LBA,'size':SIZE,'source_sha256':SOURCE_SHA,'replacement_sha256':replacement_sha,'output_sha256':shaf(a.output),'approved_footprint_sectors':len(footprint),'changed_sectors':len(changed),'parent_overlap':0,'outside_footprint_changes':0,'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'1/1 PASS','expected_write_records':len(expected),'guessed_payload_bytes':False}
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
