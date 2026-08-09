#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,shutil
from pathlib import Path
RAW=2352;SYNC=bytes([0]+[0xFF]*10+[0]);PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
EXPECT={
 'Story121':('PASS_B247_STATIC58_PLUS_STORY121_EXECUTABLE_CANDIDATE',121,'121/121 PASS'),
 'Video10':('PASS_B247_STATIC58_PLUS_VIDEO10_EXECUTABLE_CANDIDATE',10,'10/10 PASS'),
 'UI6':('PASS_B247_STATIC58_PLUS_UI6_EXECUTABLE_CANDIDATE',6,'6/6 PASS')}
def shab(b):return hashlib.sha256(b).hexdigest()
def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024):h.update(c)
 return h.hexdigest()
def _edc_lut():
 o=[]
 for i in range(256):
  v=i
  for _ in range(8):v=(v>>1)^(0xD8018001 if v&1 else 0)
  o.append(v&0xffffffff)
 return o
EDC=_edc_lut()
def edc(d):
 v=0
 for x in d:v=(v>>8)^EDC[(v^x)&255]
 return v&0xffffffff
def _ecc_luts():
 f=[0]*256;b=[0]*256
 for i in range(256):
  j=(i<<1)^(0x11D if i&0x80 else 0);f[i]=j&255;b[i^f[i]]=i
 return f,b
EF,EB=_ecc_luts()
def ecc(src,maj,minc,mult,inc):
 size=maj*minc;o=bytearray(maj*2)
 for m in range(maj):
  idx=(m>>1)*mult+(m&1);a=b=0
  for _ in range(minc):
   t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
 return bytes(o)
def verify(s):return len(s)==RAW and s[:12]==SYNC and s[15]==1 and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and s[0x814:0x81c]==bytes(8) and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88)
def diffs(a,b):
 out=set();i=0
 with a.open('rb') as x,b.open('rb') as y:
  while True:
   p=x.read(RAW);q=y.read(RAW)
   if not p and not q:break
   if len(p)!=len(q):raise ValueError('disc size mismatch')
   if p!=q:out.add(i)
   i+=1
 return out
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def whole_gate(label,r):
 if label=='Story121':return r.get('final_whole_asset_reextraction')
 return r.get('whole_asset_reextraction')
def main():
 ap=argparse.ArgumentParser(description='Compose exact Story121 + Video10 + UI6 candidates over exact Batch247')
 ap.add_argument('--parent',type=Path,required=True)
 for n in ('story121','video10','ui6'):
  ap.add_argument(f'--{n}-bin',type=Path,required=True);ap.add_argument(f'--{n}-result',type=Path,required=True)
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B267_B247_STORY121_VIDEO10_UI6_KO.bin'))
 ap.add_argument('--result',type=Path,default=Path('BATCH267_RESULT.json'));a=ap.parse_args()
 if shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA mismatch')
 comps=[('Story121',a.story121_bin,a.story121_result),('Video10',a.video10_bin,a.video10_result),('UI6',a.ui6_bin,a.ui6_result)]
 sets={};results={}
 for label,bp,rp in comps:
  r=load(rp);status,count,wg=EXPECT[label]
  if r.get('status')!=status:raise SystemExit(f'{label} status gate failed')
  if r.get('parent_sha256')!=PARENT_SHA:raise SystemExit(f'{label} parent lineage failed')
  if shaf(bp)!=r.get('output_sha256'):raise SystemExit(f'{label} output SHA failed')
  if whole_gate(label,r)!=wg:raise SystemExit(f'{label} whole-asset gate failed')
  if 'PASS' not in str(r.get('changed_sector_edc_ecc','')):raise SystemExit(f'{label} EDC/ECC gate failed')
  ds=diffs(a.parent,bp)
  if not ds:raise SystemExit(f'{label} has zero changed sectors')
  sets[label]=ds;results[label]=r
 labels=list(sets)
 for i,x in enumerate(labels):
  for y in labels[i+1:]:
   ov=sets[x]&sets[y]
   if ov:raise SystemExit(f'component collision {x}/{y} at LBA {min(ov)}')
 shutil.copyfile(a.parent,a.output);expected=[];owners={}
 try:
  with a.parent.open('rb') as par,a.output.open('r+b') as dst:
   for label,bp,_ in comps:
    with bp.open('rb') as src:
     for lba in sorted(sets[label]):
      par.seek(lba*RAW);base=par.read(RAW);src.seek(lba*RAW);new=src.read(RAW)
      if len(base)!=RAW or len(new)!=RAW or base==new:raise ValueError(f'Expected Write mismatch {label} {lba}')
      if not verify(new):raise ValueError(f'component EDC/ECC fail {label} {lba}')
      dst.seek(lba*RAW);dst.write(new);owners[lba]=label
      expected.append({'component':label,'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(new)})
  union=set().union(*sets.values());actual=diffs(a.parent,a.output)
  if actual!=union:raise ValueError('final changed-sector accounting mismatch')
  with a.output.open('rb') as out:
   handles={label:bp.open('rb') for label,bp,_ in comps}
   try:
    for lba in sorted(actual):
     out.seek(lba*RAW);s=out.read(RAW)
     if not verify(s):raise ValueError(f'final EDC/ECC fail {lba}')
     h=handles[owners[lba]];h.seek(lba*RAW)
     if s!=h.read(RAW):raise ValueError(f'component-sector identity fail {lba}')
   finally:
    for h in handles.values():h.close()
  res={'batch':267,'status':'PASS_B247_STATIC58_PLUS_137_ASSET_CUMULATIVE_EXECUTABLE_CANDIDATE','parent_sha256':PARENT_SHA,'components':{k:{'changed_sectors':len(sets[k]),'output_sha256':results[k]['output_sha256'],'whole_asset_gate':whole_gate(k,results[k])} for k in labels},'component_sector_overlap':0,'new_replacement_assets':137,'story_controls_preserved':2,'cumulative_parent_static_plus_new_assets':195,'changed_sectors':len(actual),'expected_write_records':len(expected),'changed_sector_accounting':f'{len(actual)}/{len(actual)} PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','final_component_sector_identity':f'{len(actual)}/{len(actual)} PASS','whole_asset_reextraction_preservation':'PASS_BY_COMPONENT_WHOLE_ASSET_GATES_PLUS_DISJOINT_EXACT_SECTOR_COMPOSITION','output_sha256':shaf(a.output),'guessed_payload_bytes':False}
  a.result.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2));return 0
 except Exception:
  a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
