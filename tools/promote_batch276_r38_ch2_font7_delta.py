#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

RAW=2352; USER=2048; UOFF=16; SYNC=bytes([0]+[0xFF]*10+[0])
R37_SHA="56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736"
R38_SHA="5869491e19b4316c61725910561ec47c3f60af1983b4eae9996c5aed9e1cfd8c"
PARENT_STATUS="PASS_BATCH274_PLUS_R37_RUNTIME_SUPPORT5_EXECUTABLE_CANDIDATE"
SUCCESS="PASS_BATCH275_PLUS_R38_CH2_FONT7_DELTA_EXECUTABLE_CANDIDATE"
ASSETS=[
 ("SAKURA1/SK0201.BIN",44822,75700),
 ("SAKURA1/SK0202.BIN",44859,232536),
 ("SAKURA1/SK0203.BIN",44973,77196),
 ("SAKURA1/SK0205.BIN",45012,53728),
 ("SAKURA1/SK0206.BIN",45039,207384),
 ("SAKURA1/SK0207.BIN",45141,83924),
 ("SAKURA1/SK0208.BIN",45182,38652),
]

def hb(b): return hashlib.sha256(b).hexdigest()
def hf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024): h.update(c)
 return h.hexdigest()

def edc_lut():
 o=[]
 for i in range(256):
  v=i
  for _ in range(8): v=(v>>1)^(0xD8018001 if v&1 else 0)
  o.append(v&0xffffffff)
 return o
EDC=edc_lut()
def edc(d):
 v=0
 for x in d: v=(v>>8)^EDC[(v^x)&255]
 return v&0xffffffff

def ecc_lut():
 f=[0]*256;b=[0]*256
 for i in range(256):
  j=((i<<1)^(0x11D if i&0x80 else 0))&255;f[i]=j;b[i^j]=i
 return f,b
EF,EB=ecc_lut()
def ecc(src,major,minor,mult,inc):
 size=major*minor;o=bytearray(major*2)
 for m in range(major):
  idx=(m>>1)*mult+(m&1);a=b=0
  for _ in range(minor):
   t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+major]=a^b
 return bytes(o)

def valid(s):
 return (len(s)==RAW and s[:12]==SYNC and s[15]==1 and
  int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and
  s[0x814:0x81c]==bytes(8) and
  s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and
  s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88))

def rebuild(s):
 if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1: raise SystemExit('invalid MODE1 sector header')
 b=bytearray(s)
 b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little')
 b[0x814:0x81c]=bytes(8)
 b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86)
 b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88)
 o=bytes(b)
 if not valid(o): raise SystemExit('EDC/ECC regeneration failed')
 return o

def asset(p,lba,size):
 out=bytearray();rem=size;cur=lba
 with p.open('rb') as f:
  while rem:
   n=min(USER,rem);f.seek(cur*RAW+UOFF);c=f.read(n)
   if len(c)!=n: raise SystemExit(f'short extraction at LBA {cur}')
   out+=c;rem-=n;cur+=1
 return bytes(out)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--batch275',type=Path,required=True)
 ap.add_argument('--batch275-result',type=Path,required=True)
 ap.add_argument('--r37',type=Path,required=True)
 ap.add_argument('--r38',type=Path,required=True)
 ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--result',type=Path,required=True)
 a=ap.parse_args()
 if hf(a.r37)!=R37_SHA: raise SystemExit('exact R37 donor Disc SHA mismatch')
 if hf(a.r38)!=R38_SHA: raise SystemExit('exact R38 donor Disc SHA mismatch')
 parent_sha=hf(a.batch275)
 pr=json.loads(a.batch275_result.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha:
  raise SystemExit('Batch275 parent proof mismatch')

 plans=[]
 total_delta=0
 for path,lba,size in ASSETS:
  r37=asset(a.r37,lba,size);r38=asset(a.r38,lba,size);par=asset(a.batch275,lba,size)
  delta=[i for i,(x,y) in enumerate(zip(r37,r38)) if x!=y]
  if not delta: raise SystemExit(f'no R37->R38 donor delta: {path}')
  conflicts=[];already=0
  exp=bytearray(par)
  for i in delta:
   if par[i]==r38[i]: already+=1;exp[i]=r38[i]
   elif par[i]==r37[i]: exp[i]=r38[i]
   else: conflicts.append(i)
  if conflicts:
   raise SystemExit(f'parent conflicts with exact R37/R38 delta: {path} count={len(conflicts)} first={conflicts[0]}')
  plans.append({'path':path,'lba':lba,'size':size,'r37':r37,'r38':r38,'parent':par,'expected':bytes(exp),'delta':delta,'already':already})
  total_delta+=len(delta)

 shutil.copyfile(a.batch275,a.out)
 expected_writes=[];touched=set();asset_audit=[]
 with a.out.open('r+b') as f:
  for p in plans:
   by_sector={}
   for off in p['delta']:
    sec=off//USER;within=off%USER
    by_sector.setdefault(sec,[]).append(within)
   for sec,offs in sorted(by_sector.items()):
    lba=p['lba']+sec;f.seek(lba*RAW);before=f.read(RAW)
    if not valid(before): raise SystemExit(f'invalid parent MODE1 sector LBA {lba}')
    b=bytearray(before);base=sec*USER
    changed=0
    for within in offs:
     ai=base+within
     want=p['r38'][ai]
     if b[UOFF+within]!=want:
      # prewrite conflict was checked against whole extracted parent; this is an identity re-check.
      if b[UOFF+within]!=p['r37'][ai]: raise SystemExit(f'prewrite byte drift {p["path"]} off={ai}')
      b[UOFF+within]=want;changed+=1
    if not changed: continue
    after=rebuild(bytes(b))
    if lba in touched: raise SystemExit(f'cross-asset LBA overlap {lba}')
    f.seek(lba*RAW);f.write(after);touched.add(lba)
    expected_writes.append({'lba':lba,'iso_path':p['path'],'before_sha256':hb(before),'after_sha256':hb(after),'changed_user_bytes':changed})

 # Expected Write + EDC/ECC reread gate.
 with a.out.open('rb') as f:
  for e in expected_writes:
   f.seek(e['lba']*RAW);s=f.read(RAW)
   if hb(s)!=e['after_sha256'] or not valid(s): raise SystemExit(f'Expected Write/EDC-ECC failed LBA {e["lba"]}')

 # Exact changed-sector accounting against Batch275.
 actual=[]
 with a.batch275.open('rb') as x,a.out.open('rb') as y:
  lba=0
  while True:
   bx=x.read(RAW);by=y.read(RAW)
   if not bx and not by: break
   if len(bx)!=len(by): raise SystemExit('disc length mismatch')
   if bx!=by: actual.append(lba)
   lba+=1
 if actual!=sorted(touched): raise SystemExit('changed-sector accounting mismatch')

 # Whole-asset re-extraction: final asset must equal parent + exact donor delta, byte-for-byte.
 for p in plans:
  got=asset(a.out,p['lba'],p['size']);ok=got==p['expected']
  asset_audit.append({'iso_path':p['path'],'r37_sha256':hb(p['r37']),'r38_sha256':hb(p['r38']),'parent_sha256':hb(p['parent']),'expected_merged_sha256':hb(p['expected']),'actual_sha256':hb(got),'delta_bytes':len(p['delta']),'already_r38_bytes':p['already'],'pass':ok})
  if not ok: raise SystemExit(f'whole-asset merged re-extraction failed: {p["path"]}')

 result={
  'batch':276,'status':SUCCESS,'parent_batch':275,'parent_sha256':parent_sha,
  'r37_disc_sha256':R37_SHA,'r38_disc_sha256':R38_SHA,'output_sha256':hf(a.out),
  'assets':'7/7 PASS','exact_donor_delta_bytes':total_delta,'changed_raw_sectors':len(touched),
  'expected_write_records':len(expected_writes),'mode1_edc_ecc':f'{len(touched)}/{len(touched)} PASS',
  'whole_asset_reextraction':'7/7 PASS','asset_audit':asset_audit,'expected_write':expected_writes,
  'preservation_rule':'all Batch275 bytes outside exact R37->R38 donor delta preserved','guessed_payload_bytes':0
 }
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:result[k] for k in ('status','output_sha256','exact_donor_delta_bytes','changed_raw_sectors','whole_asset_reextraction')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
