#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

RAW=2352
SYNC=bytes([0]+[0xFF]*10+[0])
PARENT_STATUS='PASS_BATCH275_PLUS_R38_CH2_FONT7_DELTA_EXECUTABLE_CANDIDATE'
B277_STATUS='PASS_BATCH276_PLUS_R39_FONT2_DELTA_EXECUTABLE_CANDIDATE'
SUCCESS='PASS_BATCH278_B277_FINAL_RELEASE_GATE'

def hf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024): h.update(c)
 return h.hexdigest()

def hb(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def edc_lut():
 out=[]
 for i in range(256):
  v=i
  for _ in range(8): v=(v>>1)^(0xD8018001 if v&1 else 0)
  out.append(v&0xffffffff)
 return out
EDC=edc_lut()
def edc(d:bytes)->int:
 v=0
 for x in d: v=(v>>8)^EDC[(v^x)&255]
 return v&0xffffffff

def ecc_lut():
 f=[0]*256;b=[0]*256
 for i in range(256):
  j=((i<<1)^(0x11D if i&0x80 else 0))&255;f[i]=j;b[i^j]=i
 return f,b
EF,EB=ecc_lut()
def ecc(src:bytes,major:int,minor:int,mult:int,inc:int)->bytes:
 size=major*minor;o=bytearray(major*2)
 for m in range(major):
  idx=(m>>1)*mult+(m&1);a=b=0
  for _ in range(minor):
   t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+major]=a^b
 return bytes(o)

def valid_mode1(s:bytes)->bool:
 return (len(s)==RAW and s[:12]==SYNC and s[15]==1 and
  int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and
  s[0x814:0x81c]==bytes(8) and
  s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and
  s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88))

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--batch276',type=Path,required=True)
 ap.add_argument('--batch276-result',type=Path,required=True)
 ap.add_argument('--batch277',type=Path,required=True)
 ap.add_argument('--batch277-result',type=Path,required=True)
 ap.add_argument('--result',type=Path,required=True)
 a=ap.parse_args()

 sha276=hf(a.batch276); sha277=hf(a.batch277)
 r276=json.loads(a.batch276_result.read_text(encoding='utf-8'))
 r277=json.loads(a.batch277_result.read_text(encoding='utf-8'))
 if r276.get('status')!=PARENT_STATUS or r276.get('output_sha256')!=sha276:
  raise SystemExit('Batch276 proof/SHA binding failed')
 if r277.get('status')!=B277_STATUS or r277.get('parent_sha256')!=sha276 or r277.get('output_sha256')!=sha277:
  raise SystemExit('Batch277 proof/SHA binding failed')
 if r277.get('guessed_payload_bytes')!=0:
  raise SystemExit('guessed payload bytes must be zero')
 if r277.get('assets')!='2/2 PASS' or r277.get('whole_asset_reextraction')!='2/2 PASS':
  raise SystemExit('Batch277 whole-asset gate not closed')
 audits=r277.get('asset_audit') or []
 if len(audits)!=2 or not all(x.get('pass') is True for x in audits):
  raise SystemExit('Batch277 asset audit is not 2/2 PASS')
 writes=r277.get('expected_write') or []
 by_lba={int(x['lba']):x for x in writes}
 if len(by_lba)!=len(writes): raise SystemExit('duplicate Expected Write LBA')

 actual=[]; edc_bad=[]; expected_bad=[]
 with a.batch276.open('rb') as p,a.batch277.open('rb') as q:
  lba=0
  while True:
   bp=p.read(RAW); bq=q.read(RAW)
   if not bp and not bq: break
   if len(bp)!=len(bq) or len(bp)!=RAW: raise SystemExit('disc length/sector alignment mismatch')
   if bp!=bq:
    actual.append(lba)
    e=by_lba.get(lba)
    if e is None or e.get('before_sha256')!=hb(bp) or e.get('after_sha256')!=hb(bq): expected_bad.append(lba)
    if not valid_mode1(bq): edc_bad.append(lba)
   lba+=1
 expected=sorted(by_lba)
 if actual!=expected: raise SystemExit(f'changed-sector accounting mismatch actual={len(actual)} expected={len(expected)}')
 if expected_bad: raise SystemExit(f'Expected Write mismatch first={expected_bad[0]} count={len(expected_bad)}')
 if edc_bad: raise SystemExit(f'EDC/ECC mismatch first={edc_bad[0]} count={len(edc_bad)}')
 if r277.get('changed_raw_sectors')!=len(actual): raise SystemExit('result changed_raw_sectors mismatch')
 if r277.get('expected_write_records')!=len(writes): raise SystemExit('result expected_write_records mismatch')

 out={
  'batch':278,'status':SUCCESS,'verified_batch277_sha256':sha277,'verified_parent_batch276_sha256':sha276,
  'changed_raw_sectors':len(actual),'expected_write_records':len(writes),
  'expected_write':f'{len(writes)}/{len(writes)} PASS','mode1_edc_ecc':f'{len(actual)}/{len(actual)} PASS',
  'changed_sector_accounting':'PASS','whole_asset_audit':'2/2 PASS','whole_asset_reextraction':'2/2 PASS',
  'guessed_payload_bytes':0
 }
 a.result.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
