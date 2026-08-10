#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
SOURCE_SHA="d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
B288_STATUS="PASS_BATCH288_B287_PLUS_R37_UI3_RUNTIME5_EXACT_UNION"
B267_STATUS="PASS_B247_STATIC58_PLUS_137_ASSET_CUMULATIVE_EXECUTABLE_CANDIDATE"
PASS_STATUS="PASS_BATCH289_B288_PLUS_B267_TITLECARD6_EXACT_UNION"
ASSETS=[
("SAKURA1/SK2MV_43.CAK",161590,7663544,"4f6292715c418a05f2318ac408d136833ca502d8ce969d3d3be4587a99085b9c"),
("SAKURA1/SK2MV_44.CAK",165332,7663952,"7827f423244c1ebfce486eb32fc6a032cb617890ec1cfd37b5e4f4072c14b7d6"),
("SAKURA1/SK2MV_45.CAK",169075,7656708,"f6689b9814b2dc883bf5817e286926f3f42ac334786725daf2b6a241383574e1"),
("SAKURA1/SK2MV_46.CAK",172814,7496584,"405630c16ba47c6a5786d2c6e1788d8dbdac1da39f5fb4a79ad91a3998935a24"),
("SAKURA1/SK2MV_47.CAK",176475,7633772,"2493b5c93567683d6b84b1787d772a4ce9d215dc6445eac6ca9cc1e1c9abf545"),
("SAKURA1/SK2MV_48.CAK",180203,7615920,"49267efd021d9d11f6e02b45550e045a7c784eac6f1e8b83986a56b22fd462e5")]

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
 ap=argparse.ArgumentParser(description='Batch289 exact six episode-title CAK union onto successful Batch288')
 ap.add_argument('--parent-bin',required=True,type=Path); ap.add_argument('--b288-report',required=True,type=Path)
 ap.add_argument('--source-bin',required=True,type=Path); ap.add_argument('--b267-bin',required=True,type=Path)
 ap.add_argument('--b267-report',required=True,type=Path); ap.add_argument('--output-bin',required=True,type=Path); ap.add_argument('--report',required=True,type=Path)
 a=ap.parse_args()
 for p in (a.parent_bin,a.source_bin,a.b267_bin):
  if p.stat().st_size!=DISC_SIZE: raise SystemExit(f'FAIL disc size {p}')
 parent_sha,source_sha,donor_sha=shaf(a.parent_bin),shaf(a.source_bin),shaf(a.b267_bin)
 if source_sha!=SOURCE_SHA: raise SystemExit('FAIL pristine Disc1 SHA binding')
 bind_report(a.b288_report,B288_STATUS,parent_sha,'Batch288'); bind_report(a.b267_report,B267_STATUS,donor_sha,'Batch267')
 parent=a.parent_bin.read_bytes(); source=a.source_bin.read_bytes(); donor=a.b267_bin.read_bytes()
 asset_lbas=set(); audit=[]
 for path,lba,size,target_sha in ASSETS:
  got=shab(extract(donor,lba,size))
  if got!=target_sha: raise SystemExit(f'FAIL Batch267 donor whole-asset SHA {path}')
  asset_lbas.update(range(lba,lba+(size+USER_SIZE-1)//USER_SIZE))
 delta=[]
 for lba in sorted(asset_lbas):
  off=lba*RAW_SECTOR_SIZE; before=source[off:off+RAW_SECTOR_SIZE]; after=donor[off:off+RAW_SECTOR_SIZE]
  if before!=after:
   if not verify_mode1_sector(after)['valid']: raise SystemExit(f'FAIL donor EDC/ECC LBA {lba}')
   delta.append((lba,shab(before),shab(after)))
 if not delta: raise SystemExit('FAIL empty titlecard6 donor delta')
 out=bytearray(parent); ew=[]; already=0
 for lba,bsha,asha in delta:
  off=lba*RAW_SECTOR_SIZE; cur=bytes(parent[off:off+RAW_SECTOR_SIZE]); csha=shab(cur)
  if csha==asha: already+=1; continue
  if csha!=bsha: raise SystemExit(f'FAIL third variant LBA {lba}: parent={csha} pristine={bsha} target={asha}')
  ew.append({'lba':lba,'before_sha256':bsha,'after_sha256':asha}); out[off:off+RAW_SECTOR_SIZE]=donor[off:off+RAW_SECTOR_SIZE]
 actual=[]
 for lba in sorted(asset_lbas):
  off=lba*RAW_SECTOR_SIZE
  if parent[off:off+RAW_SECTOR_SIZE]!=out[off:off+RAW_SECTOR_SIZE]: actual.append(lba)
 if actual!=[x['lba'] for x in ew]: raise SystemExit('FAIL changed-LBA accounting')
 for w in ew:
  off=w['lba']*RAW_SECTOR_SIZE; sec=bytes(out[off:off+RAW_SECTOR_SIZE])
  if shab(sec)!=w['after_sha256'] or not verify_mode1_sector(sec)['valid']: raise SystemExit(f"FAIL final sector gate LBA {w['lba']}")
 for path,lba,size,target_sha in ASSETS:
  final=shab(extract(out,lba,size))
  if final!=target_sha: raise SystemExit(f'FAIL final whole-asset re-extraction {path}')
  audit.append({'path':path,'lba':lba,'size':size,'sha256':final,'status':'PASS'})
 a.output_bin.parent.mkdir(parents=True,exist_ok=True); a.output_bin.write_bytes(out); output_sha=shaf(a.output_bin)
 report={'batch':289,'status':PASS_STATUS,'parent_batch':288,'parent_sha256':parent_sha,'source_sha256':source_sha,'donor_batch':267,'donor_sha256':donor_sha,'asset_count':6,'derived_titlecard_delta_sectors':len(delta),'already_target_sectors':already,'expected_write_count':len(ew),'expected_write':ew,'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','whole_asset_reextraction':'6/6 PASS','asset_audit':audit,'event_mes_logical_completion':'109/109','static_assets_verified':58,'speech_movies_physical':'12/12','episode_title_cards_physical':'6/6','title_assets_physical':'3/3','additional_ui_assets_physical':'3/3','runtime_support_assets_physical':'5/5','guessed_payload_bytes':0,'output_sha256':output_sha}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(PASS_STATUS); print(f'output_sha256={output_sha}'); print(f'changed_raw_sectors={len(actual)}'); print('whole_asset_reextraction=6/6 PASS')
if __name__=='__main__': main()
