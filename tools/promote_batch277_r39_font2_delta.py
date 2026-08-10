#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

RAW=2352; USER=2048; UOFF=16; SYNC=bytes([0]+[0xFF]*10+[0])
R38_SHA="5869491e19b4316c61725910561ec47c3f60af1983b4eae9996c5aed9e1cfd8c"
R39_SHA="57335616e481102fe2ef7ab080871df479211f388eff796d5c6bca7a28958025"
PARENT_STATUS="PASS_BATCH275_PLUS_R38_CH2_FONT7_DELTA_EXECUTABLE_CANDIDATE"
SUCCESS="PASS_BATCH276_PLUS_R39_FONT2_DELTA_EXECUTABLE_CANDIDATE"
ASSETS=[
 ("SAKURA2/M01LOW.BIN",219653,412480),
 ("SAKURA2/EV02001.MES",248627,71851),
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
 ap.add_argument('--batch276',type=Path,required=True)
 ap.add_argument('--batch276-result',type=Path,required=True)
 ap.add_argument('--r38',type=Path,required=True)
 ap.add_argument('--r39',type=Path,required=True)
 ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--result',type=Path,required=True)
 a=ap.parse_args()
 if hf(a.r38)!=R38_SHA: raise SystemExit('exact R38 donor Disc SHA mismatch')
 if hf(a.r39)!=R39_SHA: raise SystemExit('exact R39 donor Disc SHA mismatch')
 parent_sha=hf(a.batch276)
 pr=json.loads(a.batch276_result.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha:
  raise SystemExit('Batch276 parent proof mismatch')

 plans=[];total_delta=0
 for path,lba,size in ASSETS:
  r38=asset(a.r38,lba,size);r39=asset(a.r39,lba,size);par=asset(a.batch276,lba,size)
  delta=[i for i,(x,y) in enumerate(zip(r38,r39)) if x!=y]
  if not delta: raise SystemExit(f'no R38->R39 donor delta: {path}')
  exp=bytearray(par);conflicts=[];already=0
  for i in delta:
   if par[i]==r39[i]: already+=1;exp[i]=r39[i]
   elif par[i]==r38[i]: exp[i]=r39[i]
   else: conflicts.append(i)
  if conflicts:
   raise SystemExit(f'parent conflicts with exact R38/R39 delta: {path} count={len(conflicts)} first={conflicts[0]}')
  plans.append({'path':path,'lba':lba,'size':size,'r38':r38,'r39':r39,'parent':par,'expected':bytes(exp),'delta':delta,'already':already})
  total_delta+=len(delta)

 shutil.copyfile(a.batch276,a.out);expected_writes=[];touched=set()
 with a.out.open('r+b') as f:
  for p in plans:
   by_sector={}
   for off in p['delta']:
    by_sector.setdefault(off//USER,[]).append(off%USER)
   for sec,offs in sorted(by_sector.items()):
    lba=p['lba']+sec;f.seek(lba*RAW);before=f.read(RAW)
    if not valid(before): raise SystemExit(f'invalid parent MODE1 sector LBA {lba}')
    b=bytearray(before);base=sec*USER;changed=0
    for within in offs:
     ai=base+within;want=p['r39'][ai]
     if b[UOFF+within]!=want:
      if b[UOFF+within]!=p['r38'][ai]: raise SystemExit(f'prewrite byte drift {p["path"]} off={ai}')
      b[UOFF+within]=want;changed+=1
    if not changed: continue
    after=rebuild(bytes(b))
    if lba in touched: raise SystemExit(f'cross-asset LBA overlap {lba}')
    f.seek(lba*RAW);f.write(after);touched.add(lba)
    expected_writes.append({'lba':lba,'iso_path':p['path'],'before_sha256':hb(before),'after_sha256':hb(after),'changed_user_bytes':changed})

 with a.out.open('rb') as f:
  for e in expected_writes:
   f.seek(e['lba']*RAW);s=f.read(RAW)
   if hb(s)!=e['after_sha256'] or not valid(s): raise SystemExit(f'Expected Write/EDC-ECC failed LBA {e["lba"]}')

 actual=[]
 with a.batch276.open('rb') as x,a.out.open('rb') as y:
  lba=0
  while True:
   bx=x.read(RAW);by=y.read(RAW)
   if not bx and not by: break
   if len(bx)!=len(by): raise SystemExit('disc length mismatch')
   if bx!=by: actual.append(lba)
   lba+=1
 if actual!=sorted(touched): raise SystemExit('changed-sector accounting mismatch')

 asset_audit=[]
 for p in plans:
  got=asset(a.out,p['lba'],p['size']);ok=got==p['expected']
  asset_audit.append({'iso_path':p['path'],'r38_sha256':hb(p['r38']),'r39_sha256':hb(p['r39']),'parent_sha256':hb(p['parent']),'expected_merged_sha256':hb(p['expected']),'actual_sha256':hb(got),'delta_bytes':len(p['delta']),'already_r39_bytes':p['already'],'pass':ok})
  if not ok: raise SystemExit(f'whole-asset merged re-extraction failed: {p["path"]}')

 result={'batch':277,'status':SUCCESS,'parent_batch':276,'parent_sha256':parent_sha,
  'r38_disc_sha256':R38_SHA,'r39_disc_sha256':R39_SHA,'output_sha256':hf(a.out),
  'assets':'2/2 PASS','exact_donor_delta_bytes':total_delta,'changed_raw_sectors':len(touched),
  'historical_r38_to_r39_changed_raw_sectors':29,'expected_write_records':len(expected_writes),
  'mode1_edc_ecc':f'{len(touched)}/{len(touched)} PASS','whole_asset_reextraction':'2/2 PASS',
  'asset_audit':asset_audit,'expected_write':expected_writes,
  'preservation_rule':'all Batch276 bytes outside exact R38->R39 donor delta preserved','guessed_payload_bytes':0}
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:result[k] for k in ('status','output_sha256','exact_donor_delta_bytes','changed_raw_sectors','whole_asset_reextraction')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
