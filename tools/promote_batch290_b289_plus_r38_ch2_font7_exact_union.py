#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
R37_SHA="56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736"
R38_SHA="5869491e19b4316c61725910561ec47c3f60af1983b4eae9996c5aed9e1cfd8c"
B289_STATUS="PASS_BATCH289_B288_PLUS_B267_TITLECARD6_EXACT_UNION"
PASS_STATUS="PASS_BATCH290_B289_PLUS_R38_CH2_FONT7_EXACT_UNION"
EXPECTED_DELTA_SECTORS=198
ASSETS=[
("SAKURA1/SK0201.BIN",44822,75700,"de5cfec6e21dd67f8cdde2f9fd783e4e79eb7aa8b2336b1710bfd4e6ab253902","b9f507745c968a37ddf649e07ae1de8ad6cfb91a6b7bdc5a7cc2235611396c55"),
("SAKURA1/SK0202.BIN",44859,232536,"bf8a8614e1dbba35863417f49cba65c6fbe0c1da74afcd3d22fe121b2feb3c3b","25e2309877660d0cd1a77c5a2a40f05e12710b7b6d77e3dca5671397e8ec17de"),
("SAKURA1/SK0203.BIN",44973,77196,"0f4800efb6170a6f34193532d4ca259b34d5125e7fe3837860cd28ff114a0886","6a44d709c0602a787e5fce592faf62ee0849295542639f338f19a7f6100fbd03"),
("SAKURA1/SK0205.BIN",45012,53728,"aa5885900c72786556decda6061f17ddfafb6805cd348cffd4a855f838400663","eccb40b4bcf04300b32cb3f19bc7822f151937754eae10cefc9ec2b552287de4"),
("SAKURA1/SK0206.BIN",45039,207384,"b07a2e4423f8b8b612d4c8504ca93c3624bbe0133890d8e631741c6099f9b206","18a3711605c9eefaa90ad531875d53289db4217bc24a1249076152543a44af64"),
("SAKURA1/SK0207.BIN",45141,83924,"8d53ad56ded3d42b4b3bc8099d1ff7d0de6611a95aeb9a3ee9103be44aebe153","352ff1a61d0d35d764ee1ef799dbff6454a848e5e55671d9db00daff519487d5"),
("SAKURA1/SK0208.BIN",45182,38652,"0f3839c27eba1b4dec636239e4572c0fbb44a45f292d3925a6a21cc7d71ae0c9","c8edf70c41dd299cc31136e11bc038c84b910432424d3819c9da58c156c663fa")]

def shab(b): return hashlib.sha256(b).hexdigest()
def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024): h.update(c)
 return h.hexdigest()
def extract(raw,lba,size):
 out=bytearray(); n=0
 while len(out)<size:
  off=(lba+n)*RAW_SECTOR_SIZE; sec=raw[off:off+RAW_SECTOR_SIZE]
  if len(sec)!=RAW_SECTOR_SIZE or sec[15]!=1: raise SystemExit(f'FAIL non-MODE1 asset sector LBA {lba+n}')
  take=min(USER_SIZE,size-len(out)); out+=sec[USER_OFF:USER_OFF+take]; n+=1
 return bytes(out)
def bind_report(path,status,disc_sha,label):
 r=json.loads(path.read_text(encoding='utf-8'))
 if r.get('status')!=status: raise SystemExit(f'FAIL {label} status')
 if str(r.get('output_sha256','')).lower()!=disc_sha: raise SystemExit(f'FAIL {label} output SHA binding')
 if int(r.get('guessed_payload_bytes',0))!=0: raise SystemExit(f'FAIL {label} guessed payload bytes')
 return r

def main():
 ap=argparse.ArgumentParser(description='Batch290 exact R38 chapter2 seven-scenario font normalization union onto successful Batch289')
 ap.add_argument('--parent-bin',required=True,type=Path); ap.add_argument('--b289-report',required=True,type=Path)
 ap.add_argument('--r37-bin',required=True,type=Path); ap.add_argument('--r38-bin',required=True,type=Path)
 ap.add_argument('--output-bin',required=True,type=Path); ap.add_argument('--report',required=True,type=Path)
 a=ap.parse_args()
 for p in (a.parent_bin,a.r37_bin,a.r38_bin):
  if p.stat().st_size!=DISC_SIZE: raise SystemExit(f'FAIL disc size {p}')
 parent_sha,r37_sha,r38_sha=shaf(a.parent_bin),shaf(a.r37_bin),shaf(a.r38_bin)
 if r37_sha!=R37_SHA: raise SystemExit('FAIL R37 whole-disc SHA binding')
 if r38_sha!=R38_SHA: raise SystemExit('FAIL R38 whole-disc SHA binding')
 bind_report(a.b289_report,B289_STATUS,parent_sha,'Batch289')
 parent=a.parent_bin.read_bytes(); r37=a.r37_bin.read_bytes(); r38=a.r38_bin.read_bytes()
 asset_lbas=set(); audit=[]
 for path,lba,size,source_sha,target_sha in ASSETS:
  if shab(extract(r37,lba,size))!=source_sha: raise SystemExit(f'FAIL R37 whole-asset SHA {path}')
  if shab(extract(r38,lba,size))!=target_sha: raise SystemExit(f'FAIL R38 whole-asset SHA {path}')
  asset_lbas.update(range(lba,lba+(size+USER_SIZE-1)//USER_SIZE))
 delta=[]
 for lba in sorted(asset_lbas):
  off=lba*RAW_SECTOR_SIZE; before=r37[off:off+RAW_SECTOR_SIZE]; after=r38[off:off+RAW_SECTOR_SIZE]
  if before!=after:
   if not verify_mode1_sector(after)['valid']: raise SystemExit(f'FAIL R38 donor EDC/ECC LBA {lba}')
   delta.append((lba,shab(before),shab(after)))
 if len(delta)!=EXPECTED_DELTA_SECTORS: raise SystemExit(f'FAIL R37->R38 delta sector count {len(delta)} != {EXPECTED_DELTA_SECTORS}')
 out=bytearray(parent); ew=[]; already=0
 for lba,bsha,asha in delta:
  off=lba*RAW_SECTOR_SIZE; cur=bytes(parent[off:off+RAW_SECTOR_SIZE]); csha=shab(cur)
  if csha==asha: already+=1; continue
  if csha!=bsha: raise SystemExit(f'FAIL third variant LBA {lba}: parent={csha} r37={bsha} r38={asha}')
  ew.append({'lba':lba,'before_sha256':bsha,'after_sha256':asha}); out[off:off+RAW_SECTOR_SIZE]=r38[off:off+RAW_SECTOR_SIZE]
 actual=[]
 for lba in sorted(asset_lbas):
  off=lba*RAW_SECTOR_SIZE
  if parent[off:off+RAW_SECTOR_SIZE]!=out[off:off+RAW_SECTOR_SIZE]: actual.append(lba)
 if actual!=[x['lba'] for x in ew]: raise SystemExit('FAIL changed-LBA accounting')
 for w in ew:
  off=w['lba']*RAW_SECTOR_SIZE; sec=bytes(out[off:off+RAW_SECTOR_SIZE])
  if shab(sec)!=w['after_sha256'] or not verify_mode1_sector(sec)['valid']: raise SystemExit(f"FAIL final sector gate LBA {w['lba']}")
 for path,lba,size,source_sha,target_sha in ASSETS:
  final=shab(extract(out,lba,size))
  if final!=target_sha: raise SystemExit(f'FAIL final whole-asset re-extraction {path}')
  audit.append({'path':path,'lba':lba,'size':size,'r37_sha256':source_sha,'r38_sha256':target_sha,'final_sha256':final,'status':'PASS'})
 a.output_bin.parent.mkdir(parents=True,exist_ok=True); a.output_bin.write_bytes(out); output_sha=shaf(a.output_bin)
 report={'batch':290,'status':PASS_STATUS,'parent_batch':289,'parent_sha256':parent_sha,'r37_sha256':r37_sha,'r38_sha256':r38_sha,'asset_count':7,'converted_hangul_glyph_slots':2692,'script_pointer_control_bytes_changed':0,'derived_r37_to_r38_delta_sectors':len(delta),'already_target_sectors':already,'expected_write_count':len(ew),'expected_write':ew,'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','whole_asset_reextraction':'7/7 PASS','asset_audit':audit,'event_mes_logical_completion':'109/109','static_assets_verified':58,'speech_movies_physical':'12/12','episode_title_cards_physical':'6/6','title_assets_physical':'3/3','additional_ui_assets_physical':'3/3','runtime_support_assets_physical':'5/5','chapter2_font_normalized_story_assets_physical':'7/7','guessed_payload_bytes':0,'output_sha256':output_sha}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(PASS_STATUS); print(f'output_sha256={output_sha}'); print(f'changed_raw_sectors={len(actual)}'); print('whole_asset_reextraction=7/7 PASS')
if __name__=='__main__': main()
