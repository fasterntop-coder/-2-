#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path

PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
B247_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
CONTROLS=[
 {'iso_path':'SAKURA2/EV00001.MES','lba':247589,'size':16,'source_sha256':'374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb'},
 {'iso_path':'SAKURA2/EV26001.MES','lba':247615,'size':16,'source_sha256':'374708fff7719dd5979ec875d56cd2286f6d3cf7ec317a3b25632aab28ec37bb'}
]

def shaf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024):h.update(c)
 return h.hexdigest()

def canonical(x:dict)->dict:
 return {k:x[k] for k in ('iso_path','lba','size','source_sha256','replacement_sha256')}

def main()->int:
 ap=argparse.ArgumentParser(description='Build exact 107-replacement + 2-control Story109 physical promotion manifest')
 ap.add_argument('--story75-manifest',type=Path,required=True)
 ap.add_argument('--story85-sourceset',type=Path,default=Path('manifests/CD1_BATCH250_STORY85_SOURCESET.json'))
 ap.add_argument('--early22',type=Path,default=Path('manifests/CD1_BATCH252_EARLY22_EXACT_RECOVERY.json'))
 ap.add_argument('--output',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
 a=ap.parse_args()
 s75=json.loads(a.story75_manifest.read_text(encoding='utf-8'))
 s85=json.loads(a.story85_sourceset.read_text(encoding='utf-8'))
 e22=json.loads(a.early22.read_text(encoding='utf-8'))
 if s75.get('format')!='ST2-CD1-BATCH249-STORY75-MEGA-PROMOTION-v1' or len(s75.get('replacement_files',[]))!=75:raise SystemExit('Story75 manifest gate failed')
 if s75.get('physical_parent_disc_sha256')!=B247_SHA or s75.get('pristine_disc_sha256')!=PRISTINE_SHA:raise SystemExit('Story75 lineage mismatch')
 if s85.get('format')!='ST2-CD1-BATCH250-STORY85-SOURCESET-v1' or len(s85.get('additional_exact_assets',[]))!=10:raise SystemExit('Story85 source-set gate failed')
 if e22.get('format')!='ST2-CD1-BATCH252-EARLY22-EXACT-RECOVERY-v1' or len(e22.get('assets',[]))!=22:raise SystemExit('Early22 gate failed')
 merged={}; provenance=[]
 groups=[('Story75',s75['replacement_files']),('Story85Additional10',s85['additional_exact_assets']),('Early22',e22['assets'])]
 for label,xs in groups:
  provenance.append({'group':label,'assets':len(xs)})
  for raw in xs:
   x=canonical(raw); key=x['iso_path']
   if key in merged and merged[key]!=x:raise SystemExit(f'conflicting duplicate: {key}')
   merged[key]=x
 assets=sorted(merged.values(),key=lambda x:(x['lba'],x['iso_path']))
 if len(assets)!=107:raise SystemExit(f'unique replacement count {len(assets)} != 107')
 if len({Path(x['iso_path']).name for x in assets})!=107:raise SystemExit('duplicate replacement basenames')
 footprint={}; replacement_sectors=set()
 for x in assets:
  ls=set(range(x['lba'],x['lba']+math.ceil(x['size']/2048)))
  hit=replacement_sectors&ls
  if hit:raise SystemExit(f'replacement footprint collision: {x["iso_path"]} LBA {min(hit)}')
  replacement_sectors|=ls; footprint[x['iso_path']]=len(ls)
 control_sectors=set()
 for c in CONTROLS:
  ls=set(range(c['lba'],c['lba']+math.ceil(c['size']/2048)))
  if ls&replacement_sectors:raise SystemExit(f'control/replacement collision: {c["iso_path"]}')
  if ls&control_sectors:raise SystemExit(f'control/control collision: {c["iso_path"]}')
  control_sectors|=ls
 out={
  'format':'ST2-CD1-BATCH253-STORY109-PROMOTION-v1','batch':253,'goal':'CD1_100_PERCENT','target_disc':1,
  'physical_parent_batch':247,'physical_parent_disc_sha256':B247_SHA,'pristine_disc_sha256':PRISTINE_SHA,
  'source_provenance':provenance,
  'replacement_asset_count':107,'control_asset_count':2,'story_files_accounted':109,
  'replacement_files':assets,'control_files':CONTROLS,
  'approved_replacement_footprint_sectors':len(replacement_sectors),'approved_control_footprint_sectors':len(control_sectors),
  'intra_replacement_footprint_collisions':0,'control_replacement_collisions':0,
  'source_file_hashes':{'story75_manifest_sha256':shaf(a.story75_manifest),'story85_sourceset_sha256':shaf(a.story85_sourceset),'early22_manifest_sha256':shaf(a.early22)},
  'policy':{'guessed_payload_bytes':False,'require_exact_candidate_sha256':True,'require_pristine_source_sha256':True,'require_parent_footprint_nonoverlap':True,'require_expected_write':True,'require_changed_sector_edc_ecc':True,'require_changed_sector_accounting':True,'require_whole_asset_reextraction':True,'require_controls_pristine':True},
  'status':'READY_FOR_107_REPLACEMENT_PLUS_2_CONTROL_PHYSICAL_PROMOTION'
 }
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':'PASS','replacement_assets':107,'controls':2,'story_files_accounted':109,'replacement_footprint_sectors':len(replacement_sectors),'output':str(a.output)},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
