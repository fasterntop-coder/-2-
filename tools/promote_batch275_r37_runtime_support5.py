#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

RAW=2352; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA="d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
R37_SHA="56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736"
PARENT_STATUS="PASS_BATCH273_PLUS_EVENT109_COMPLETE_EXECUTABLE_CANDIDATE"
SUCCESS="PASS_BATCH274_PLUS_R37_RUNTIME_SUPPORT5_EXECUTABLE_CANDIDATE"
ASSETS=[
 ("SAKURA1/BTSFONT.BIN",3943,38860,"490bbf4e2d76955b10c0e2cc8d8644210ae0b738dd9214b1a7f9bd9dde816a67"),
 ("SAKURA2/M00LOW.BIN",218758,412480,"5238a49aafd485da38f8cca297e085ac31f6fa4538971dd9f3ed2d05b72bc401"),
 ("SAKURA2/M01LOW.BIN",219653,412480,"a2fe5a5eb9400dba586e94ef21217cccde85d7c8541be9625980d7e5c5f2a6d4"),
 ("SAKURA2/M26LOW.BIN",224206,412480,"9c2dc9b8e9ed3d299719a748b41920a5fdd7995adf3a43c798540a181057c6f3"),
 ("SAKURA2/M27LOW.BIN",225106,412480,"6a9a3151b34a7417e280d44cb4486e2b90788fd7099d8da0339224e2df84927f"),
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
 return len(s)==RAW and s[:12]==SYNC and s[15]==1 and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and s[0x814:0x81c]==bytes(8) and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88)
def rebuild(s):
 if not valid(s): raise SystemExit('invalid MODE1 parent sector')
 b=bytearray(s);b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8);b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88)
 o=bytes(b)
 if not valid(o): raise SystemExit('EDC/ECC regeneration failed')
 return o
def asset(p,lba,size):
 out=bytearray();rem=size
 with p.open('rb') as f:
  while rem:
   n=min(USER,rem);f.seek(lba*RAW+16);c=f.read(n)
   if len(c)!=n: raise SystemExit('short asset extraction')
   out+=c;rem-=n;lba+=1
 return bytes(out)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch274',type=Path,required=True);ap.add_argument('--batch274-result',type=Path,required=True);ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--r37',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);a=ap.parse_args()
 if hf(a.pristine)!=PRISTINE_SHA: raise SystemExit('pristine Disc1 SHA mismatch')
 if hf(a.r37)!=R37_SHA: raise SystemExit('R37 recovery Disc SHA mismatch')
 parent_sha=hf(a.batch274);pr=json.loads(a.batch274_result.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha: raise SystemExit('Batch274 parent proof mismatch')
 recovered={};pre=[]
 for path,lba,size,target in ASSETS:
  src=asset(a.pristine,lba,size);cur=asset(a.batch274,lba,size);rep=asset(a.r37,lba,size)
  if hb(rep)!=target: raise SystemExit(f'R37 payload SHA mismatch: {path}')
  if hb(cur) not in (hb(src),target): raise SystemExit(f'unknown parent asset variant: {path}')
  recovered[path]=(lba,size,rep,target);pre.append({'iso_path':path,'pristine_sha256':hb(src),'parent_sha256':hb(cur),'replacement_sha256':target,'already_replacement':hb(cur)==target})
 shutil.copyfile(a.batch274,a.out);expected=[];touched=set()
 with a.out.open('r+b') as f:
  for path,(lba,size,rep,target) in recovered.items():
   if hb(asset(a.batch274,lba,size))==target: continue
   pos=0;rem=size;cur=lba
   while rem:
    n=min(USER,rem);f.seek(cur*RAW);before=f.read(RAW)
    if not valid(before): raise SystemExit(f'bad parent sector {cur}')
    b=bytearray(before);b[16:16+n]=rep[pos:pos+n];after=rebuild(bytes(b))
    if after!=before:
     if cur in touched: raise SystemExit(f'overlap at LBA {cur}')
     expected.append({'lba':cur,'iso_path':path,'before_sha256':hb(before),'after_sha256':hb(after)});f.seek(cur*RAW);f.write(after);touched.add(cur)
    pos+=n;rem-=n;cur+=1
 # Expected Write and EDC/ECC re-read gate
 with a.out.open('rb') as f:
  for e in expected:
   f.seek(e['lba']*RAW);s=f.read(RAW)
   if hb(s)!=e['after_sha256'] or not valid(s): raise SystemExit(f'Expected Write/EDC-ECC failed LBA {e["lba"]}')
 # exact changed-sector accounting against parent
 actual=[]
 with a.batch274.open('rb') as x,a.out.open('rb') as y:
  lba=0
  while True:
   bx=x.read(RAW);by=y.read(RAW)
   if not bx and not by: break
   if bx!=by: actual.append(lba)
   lba+=1
 if actual!=sorted(touched): raise SystemExit('changed-sector accounting mismatch')
 rex=[]
 for path,lba,size,target in ASSETS:
  got=hb(asset(a.out,lba,size));rex.append({'iso_path':path,'expected_sha256':target,'actual_sha256':got,'pass':got==target})
  if got!=target: raise SystemExit(f'whole-asset re-extraction failed: {path}')
 result={'batch':275,'status':SUCCESS,'parent_batch':274,'parent_sha256':parent_sha,'output_sha256':hf(a.out),'assets':'5/5 PASS','changed_raw_sectors':len(touched),'expected_write_records':len(expected),'mode1_edc_ecc':f'{len(touched)}/{len(touched)} PASS','whole_asset_reextraction':'5/5 PASS','prewrite_gate':pre,'expected_write':expected,'reextraction':rex,'guessed_payload_bytes':0}
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:result[k] for k in ('status','output_sha256','changed_raw_sectors','whole_asset_reextraction')},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
