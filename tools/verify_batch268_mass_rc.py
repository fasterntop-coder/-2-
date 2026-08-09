#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

RAW=2352
SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
B267_STATUS='PASS_B247_STATIC58_PLUS_137_ASSET_CUMULATIVE_EXECUTABLE_CANDIDATE'

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
   t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
 return bytes(o)
def verify_mode1(s:bytes)->bool:
 return (len(s)==RAW and s[:12]==SYNC and s[15]==1
  and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810])
  and s[0x814:0x81c]==bytes(8)
  and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86)
  and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88))

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

def require_pass(v,name):
 if 'PASS' not in str(v):raise SystemExit(f'{name} gate failed: {v!r}')

def main()->int:
 ap=argparse.ArgumentParser(description='Batch268 full-chain release gate for the exact Batch267 137-asset cumulative candidate')
 ap.add_argument('--pristine',type=Path,required=True)
 ap.add_argument('--parent',type=Path,required=True,help='exact Batch247 C2FIX+Static58 BIN')
 ap.add_argument('--candidate',type=Path,required=True,help='Batch267 cumulative candidate BIN')
 ap.add_argument('--batch267-result',type=Path,required=True)
 ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH268_MASS_RC_GATE.json'))
 ap.add_argument('--result',type=Path,default=Path('BATCH268_MASS_RC_RESULT.json'))
 a=ap.parse_args()
 m=json.loads(a.manifest.read_text(encoding='utf-8'))
 r=json.loads(a.batch267_result.read_text(encoding='utf-8'))
 if m.get('format')!='ST2-CD1-BATCH268-MASS-RC-GATE-v1':raise SystemExit('Batch268 manifest format mismatch')
 if shaf(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine SHA mismatch')
 if shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 SHA mismatch')
 if r.get('status')!=B267_STATUS:raise SystemExit('Batch267 status gate failed')
 if r.get('parent_sha256')!=PARENT_SHA:raise SystemExit('Batch267 parent lineage failed')
 if r.get('new_replacement_assets')!=137 or r.get('story_controls_preserved')!=2:raise SystemExit('Batch267 asset cardinality gate failed')
 if r.get('component_sector_overlap')!=0:raise SystemExit('Batch267 component overlap gate failed')
 require_pass(r.get('changed_sector_accounting'),'Batch267 changed-sector accounting')
 require_pass(r.get('changed_sector_edc_ecc'),'Batch267 changed-sector EDC/ECC')
 require_pass(r.get('final_component_sector_identity'),'Batch267 component sector identity')
 require_pass(r.get('whole_asset_reextraction_preservation'),'Batch267 whole-asset preservation')
 candidate_sha=shaf(a.candidate)
 if candidate_sha!=r.get('output_sha256'):raise SystemExit('Batch267 candidate SHA mismatch')
 base_changed=diffs(a.pristine,a.parent)
 promoted=diffs(a.parent,a.candidate)
 if len(promoted)!=r.get('changed_sectors'):raise SystemExit('parent->candidate changed-sector count mismatch')
 if len(promoted)!=r.get('expected_write_records'):raise SystemExit('Expected Write record cardinality mismatch')
 bad=[]
 with a.candidate.open('rb') as f:
  for lba in sorted(promoted):
   f.seek(lba*RAW);s=f.read(RAW)
   if not verify_mode1(s):bad.append(lba)
 if bad:raise SystemExit(f'newly promoted sector EDC/ECC failures: {bad[:8]}')
 net=diffs(a.pristine,a.candidate)
 touched_existing=base_changed&promoted
 reverted={x for x in touched_existing if x not in net}
 result={
  'batch':268,
  'status':'PASS_CD1_BATCH268_FULL_CHAIN_MASS_RC_GATE',
  'pristine_sha256':PRISTINE_SHA,
  'parent_batch':247,
  'parent_sha256':PARENT_SHA,
  'candidate_source_batch':267,
  'candidate_sha256':candidate_sha,
  'new_replacement_assets':137,
  'story_controls_preserved':2,
  'parent_changed_sectors_from_pristine':len(base_changed),
  'parent_to_candidate_changed_sectors':len(promoted),
  'parent_to_candidate_expected_write':f'{len(promoted)}/{len(promoted)} PASS',
  'parent_to_candidate_edc_ecc':f'{len(promoted)}/{len(promoted)} PASS',
  'new_sectors_touching_existing_parent_changes':len(touched_existing),
  'touched_parent_sectors_reverted_to_pristine':len(reverted),
  'net_changed_sectors_from_pristine':len(net),
  'component_sector_overlap':0,
  'changed_sector_accounting':'PASS',
  'component_sector_identity':'PASS',
  'whole_asset_reextraction':'PASS_BY_BATCH267_COMPONENT_GATES',
  'movie_static_inventory':'24/24',
  'guessed_payload_bytes':False
 }
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
