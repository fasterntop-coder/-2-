#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil
from pathlib import Path
RAW=2352; USER_OFF=16; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
STORY109_STATUS='PASS_B247_STATIC58_PLUS_STORY109_EXECUTABLE_CANDIDATE'
STORY14_STATUS='PASS_B247_PLUS_STORY14_EXECUTABLE_CANDIDATE'
DYNAMIC={
 'SK0306.BIN':{'iso_path':'SAKURA1/SK0306.BIN','lba':45428,'size':50464},
 'SK0401.BIN':{'iso_path':'SAKURA1/SK0401.BIN','lba':45453,'size':104080},
 'SK0402.BIN':{'iso_path':'SAKURA1/SK0402.BIN','lba':45504,'size':249824}
}
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
def load_json(p:Path)->dict:return json.loads(p.read_text(encoding='utf-8'))
def main()->int:
 ap=argparse.ArgumentParser(description='Batch263 compose exact Story109 + Story14 outputs over exact Batch247')
 ap.add_argument('--parent',type=Path,required=True)
 ap.add_argument('--story109-bin',type=Path,required=True);ap.add_argument('--story109-result',type=Path,required=True)
 ap.add_argument('--story14-bin',type=Path,required=True);ap.add_argument('--story14-result',type=Path,required=True)
 ap.add_argument('--story109-manifest',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
 ap.add_argument('--story11-manifest',type=Path,default=Path('manifests/CD1_BATCH259_STORY11_MEGA_PROMOTION.json'))
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B263_B247_STORY121_KO.bin'))
 ap.add_argument('--result',type=Path,default=Path('BATCH263_RESULT.json'))
 a=ap.parse_args()
 if shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA mismatch')
 r109=load_json(a.story109_result);r14=load_json(a.story14_result)
 if r109.get('status')!=STORY109_STATUS or r109.get('whole_asset_reextraction')!='107/107 PASS' or r109.get('control_reextraction')!='2/2 PASS':raise SystemExit('Story109 result gate failed')
 if r14.get('status')!=STORY14_STATUS or r14.get('whole_asset_reextraction')!='14/14 PASS':raise SystemExit('Story14 result gate failed')
 if shaf(a.story109_bin)!=r109.get('output_sha256'):raise SystemExit('Story109 output SHA mismatch')
 if shaf(a.story14_bin)!=r14.get('output_sha256'):raise SystemExit('Story14 output SHA mismatch')
 d109=diffs(a.parent,a.story109_bin);d14=diffs(a.parent,a.story14_bin)
 if not d109 or not d14:raise SystemExit('component has zero changed sectors')
 overlap=d109&d14
 if overlap:raise SystemExit(f'component changed-sector collision at LBA {min(overlap)}')
 shutil.copyfile(a.parent,a.output);expected=[]
 try:
  with a.parent.open('rb') as par,a.story109_bin.open('rb') as s109,a.story14_bin.open('rb') as s14,a.output.open('r+b') as dst:
   for label,src,ls in [('Story109',s109,d109),('Story14',s14,d14)]:
    for lba in sorted(ls):
     par.seek(lba*RAW);base=par.read(RAW);src.seek(lba*RAW);new=src.read(RAW)
     if len(base)!=RAW or len(new)!=RAW or base==new:raise ValueError(f'Expected Write mismatch {label} LBA {lba}')
     if not verify(new):raise ValueError(f'component EDC/ECC failure {label} LBA {lba}')
     dst.seek(lba*RAW);dst.write(new)
     expected.append({'component':label,'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(new)})
  actual=diffs(a.parent,a.output);union=d109|d14
  if actual!=union:raise ValueError('final changed-sector accounting mismatch')
  with a.output.open('rb') as f:
   for lba in actual:
    f.seek(lba*RAW)
    if not verify(f.read(RAW)):raise ValueError(f'final EDC/ECC failure LBA {lba}')
  m109=load_json(a.story109_manifest);m11=load_json(a.story11_manifest)
  x109=m109.get('replacement_files',[]);controls=m109.get('control_files',[]);x11=m11.get('replacement_files',[])
  if len(x109)!=107 or len(controls)!=2 or len(x11)!=11:raise ValueError('asset manifest cardinality mismatch')
  re={}
  for x in x109+x11:
   n=Path(x['iso_path']).name;h=shab(extract(a.output,x['lba'],x['size']))
   if h!=x['replacement_sha256']:raise ValueError(f'final whole-asset mismatch {n}')
   re[n]=h
  dyn=r14.get('reextracted_sha256',{})
  for n,x in DYNAMIC.items():
   want=dyn.get(n)
   if not want:raise ValueError(f'missing dynamic exact SHA {n}')
   h=shab(extract(a.output,x['lba'],x['size']))
   if h!=want:raise ValueError(f'final dynamic whole-asset mismatch {n}')
   re[n]=h
  if len(re)!=121:raise ValueError(f'final replacement re-extraction cardinality {len(re)} != 121')
  for c in controls:
   n=Path(c['iso_path']).name;h=shab(extract(a.output,c['lba'],c['size']))
   if h!=c['source_sha256']:raise ValueError(f'final control mismatch {n}')
  result={'batch':263,'status':'PASS_B247_STATIC58_PLUS_STORY121_EXECUTABLE_CANDIDATE','parent_batch':247,'parent_sha256':PARENT_SHA,'component_story109_changed_sectors':len(d109),'component_story14_changed_sectors':len(d14),'component_sector_overlap':0,'changed_sectors':len(actual),'expected_write_records':len(expected),'changed_sector_accounting':f'{len(actual)}/{len(actual)} PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','new_replacement_assets':121,'story_controls_preserved':2,'final_whole_asset_reextraction':'121/121 PASS','final_control_reextraction':'2/2 PASS','cumulative_parent_static_plus_new_assets':179,'output_sha256':shaf(a.output),'guessed_payload_bytes':False,'reextracted_sha256':re}
  a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except Exception:
  a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
