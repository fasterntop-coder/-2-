#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824
USER_OFF=16
USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_STATUS='PASS_BATCH303_B302_PLUS_B63_EPISODE_TITLE_CAK6_EXACT_UNION'
SUCCESS='PASS_BATCH304_B303_PLUS_B56_60_STORY_BIN5_EXACT_UNION'
FORMAT='ST2-CD1-batch304-b303-plus-b56-60-story-bin5-exact-union-v1'
EXPECTED_ASSETS=5
EXPECTED_REVIEWED=3273
EXPECTED_TRANSLATED=3268
EXPECTED_CONTROLS=5

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()

def extract(raw:bytes|bytearray,lba:int,size:int)->bytes:
 out=bytearray();i=0
 while len(out)<size:
  off=(lba+i)*RAW_SECTOR_SIZE;sec=raw[off:off+RAW_SECTOR_SIZE]
  if len(sec)!=RAW_SECTOR_SIZE or sec[15]!=1:raise SystemExit(f'FAIL MODE1 LBA {lba+i}')
  take=min(USER_SIZE,size-len(out));out+=sec[USER_OFF:USER_OFF+take];i+=1
 return bytes(out)

def rebuild(sec:bytearray)->None:
 sec[0x810:0x814]=edc(bytes(sec[:0x810])).to_bytes(4,'little');sec[0x814:0x81C]=bytes(8)
 sec[0x81C:0x8C8]=_ecc_compute(bytes(sec[0x0C:0x81C]),86,24,2,86)
 sec[0x8C8:0x930]=_ecc_compute(bytes(sec[0x0C:0x8C8]),52,43,86,88)

def index_payloads(inputs:list[Path],wanted:set[str],tmp:Path)->dict[str,Path]:
 found={}
 def add_bytes(data:bytes)->None:
  d=shab(data)
  if d in wanted and d not in found:
   q=tmp/f'{d}.payload';q.write_bytes(data);found[d]=q
 def visit(p:Path)->None:
  if p.suffix.lower()=='.zip':
   try:
    with zipfile.ZipFile(p) as z:
     for n in z.infolist():
      if not n.is_dir():add_bytes(z.read(n))
   except zipfile.BadZipFile:pass
  else:
   try:
    d=shaf(p)
    if d in wanted and d not in found:found[d]=p
   except OSError:pass
 for root in inputs:
  if root.is_dir():
   for p in root.rglob('*'):
    if p.is_file():visit(p)
  elif root.is_file():visit(root)
 return found

def validate_assets(m:dict)->list[dict]:
 rows=m.get('assets',[])
 if len(rows)!=EXPECTED_ASSETS:raise SystemExit(f'FAIL asset count {len(rows)} != {EXPECTED_ASSETS}')
 seen_name=set();ranges=[]
 reviewed=translated=controls=0
 for r in rows:
  for k in ('asset','batch','iso_path','lba','size','source_sha256','candidate_sha256','records_reviewed','translated_records','control_preserved'):
   if k not in r:raise SystemExit(f'FAIL missing {k}')
  name=str(r['asset']);lba=int(r['lba']);size=int(r['size'])
  if name in seen_name:raise SystemExit(f'FAIL duplicate asset {name}')
  seen_name.add(name)
  for k in ('source_sha256','candidate_sha256'):
   v=str(r[k]).lower()
   if len(v)!=64 or any(c not in '0123456789abcdef' for c in v):raise SystemExit(f'FAIL SHA field {name} {k}')
  if size<=0:raise SystemExit(f'FAIL size {name}')
  sectors=(size+USER_SIZE-1)//USER_SIZE;lo=lba;hi=lba+sectors-1
  for a,b,n in ranges:
   if not (hi<a or lo>b):raise SystemExit(f'FAIL overlapping LBA ranges {name}/{n}')
  ranges.append((lo,hi,name))
  reviewed+=int(r['records_reviewed']);translated+=int(r['translated_records']);controls+=int(r['control_preserved'])
 if (reviewed,translated,controls)!=(EXPECTED_REVIEWED,EXPECTED_TRANSLATED,EXPECTED_CONTROLS):
  raise SystemExit(f'FAIL story record accounting {reviewed}/{translated}/{controls}')
 return rows

def main():
 ap=argparse.ArgumentParser(description='Promote exact Batch56-60 five Korean story BIN candidates onto Batch303.')
 ap.add_argument('--parent-bin',type=Path,required=True)
 ap.add_argument('--parent-report',type=Path,required=True)
 ap.add_argument('--union-manifest',type=Path,required=True)
 ap.add_argument('--payload-input',type=Path,action='append',required=True)
 ap.add_argument('--output-bin',type=Path,required=True)
 ap.add_argument('--report',type=Path,required=True)
 a=ap.parse_args()
 if a.parent_bin.stat().st_size!=DISC_SIZE:raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin);pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha:raise SystemExit('FAIL Batch303 parent report/SHA binding')
 m=json.loads(a.union_manifest.read_text(encoding='utf-8'))
 if m.get('format')!=FORMAT or m.get('parent_batch')!=303 or m.get('batch')!=304:raise SystemExit('FAIL B304 manifest format/header')
 hs=m.get('historical_source',{})
 if hs.get('status')!='PASS_OFFLINE' or hs.get('assets')!=5 or hs.get('records_reviewed')!=EXPECTED_REVIEWED or hs.get('translated_records')!=EXPECTED_TRANSLATED or hs.get('control_preserved_records')!=EXPECTED_CONTROLS:raise SystemExit('FAIL Batch56-60 historical accounting gate')
 if hs.get('capacity_overflow')!=0 or hs.get('japanese_residual')!=0 or hs.get('reverse_decode_errors')!=0:raise SystemExit('FAIL Batch56-60 historical QA gate')
 pol=m.get('integration_policy',{})
 if pol.get('guessed_payload_bytes')!=0 or not pol.get('expected_write') or not pol.get('changed_lba_accounting') or not pol.get('changed_sector_edc_ecc') or pol.get('whole_asset_reextraction')!='5/5':raise SystemExit('FAIL integration policy')
 rows=validate_assets(m);wanted={str(r['candidate_sha256']).lower() for r in rows}
 parent=a.parent_bin.read_bytes();out=bytearray(parent);expected={};audit=[]
 with tempfile.TemporaryDirectory(prefix='st2_b304_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td));missing=wanted-set(payloads)
  if missing:raise SystemExit('FAIL missing candidate payload SHA(s): '+','.join(sorted(missing)))
  for r in rows:
   asset=r['asset'];lba=int(r['lba']);size=int(r['size']);src=str(r['source_sha256']).lower();dst=str(r['candidate_sha256']).lower()
   cur=shab(extract(out,lba,size))
   if cur not in {src,dst}:raise SystemExit(f'FAIL third variant {asset} {cur}')
   state='already_target'
   if cur==src and src!=dst:
    payload=payloads[dst].read_bytes()
    if len(payload)!=size or shab(payload)!=dst:raise SystemExit(f'FAIL payload {asset}')
    pos=idx=0
    while pos<size:
     L=lba+idx;off=L*RAW_SECTOR_SIZE;before=bytes(out[off:off+RAW_SECTOR_SIZE])
     if not verify_mode1_sector(before)['valid']:raise SystemExit(f'FAIL parent EDC/ECC LBA {L}')
     sec=bytearray(before);take=min(USER_SIZE,size-pos);sec[USER_OFF:USER_OFF+take]=payload[pos:pos+take];rebuild(sec);after=bytes(sec)
     if before!=after:
      if not verify_mode1_sector(after)['valid']:raise SystemExit(f'FAIL rebuilt EDC/ECC LBA {L}')
      ah=shab(after)
      if L in expected and expected[L]['after_sha256']!=ah:raise SystemExit(f'FAIL LBA collision {L}')
      expected[L]={'lba':L,'asset':asset,'before_sha256':shab(before),'after_sha256':ah}
      out[off:off+RAW_SECTOR_SIZE]=after
     pos+=take;idx+=1
    state='promoted_from_exact_source'
   final=shab(extract(out,lba,size))
   if final!=dst:raise SystemExit(f'FAIL whole-asset re-extraction {asset}')
   audit.append({'asset':asset,'batch':r['batch'],'lba':lba,'size':size,'parent_asset_sha256':cur,'final_asset_sha256':final,'state':state,'reextraction':'PASS','records_reviewed':r['records_reviewed'],'translated_records':r['translated_records'],'control_preserved':r['control_preserved']})
 actual=[]
 for L in range(DISC_SIZE//RAW_SECTOR_SIZE):
  off=L*RAW_SECTOR_SIZE
  if parent[off:off+RAW_SECTOR_SIZE]!=out[off:off+RAW_SECTOR_SIZE]:actual.append(L)
 if actual!=sorted(expected):raise SystemExit('FAIL changed-LBA accounting')
 for L in actual:
  off=L*RAW_SECTOR_SIZE;sec=bytes(out[off:off+RAW_SECTOR_SIZE]);rec=expected[L]
  if not verify_mode1_sector(sec)['valid']:raise SystemExit(f'FAIL final EDC/ECC LBA {L}')
  if shab(parent[off:off+RAW_SECTOR_SIZE])!=rec['before_sha256'] or shab(sec)!=rec['after_sha256']:raise SystemExit(f'FAIL Expected Write LBA {L}')
 a.output_bin.parent.mkdir(parents=True,exist_ok=True);a.output_bin.write_bytes(out);output_sha=shaf(a.output_bin)
 rep={'batch':304,'status':SUCCESS,'parent_batch':303,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'union_manifest_sha256':shaf(a.union_manifest),'replacement_assets':5,'story_records_reviewed':EXPECTED_REVIEWED,'story_records_translated':EXPECTED_TRANSLATED,'story_controls_preserved':EXPECTED_CONTROLS,'historical_story_metric':'14865/14875 = 99.9%','hardware_validation':'PENDING','guessed_payload_bytes':0,'asset_reextraction':'5/5 PASS','expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS);print('output_sha256='+output_sha);print('story_assets=5/5');print('story_records=3268 translated + 5 control');print(f'changed_raw_sectors={len(actual)}');print('guessed_payload_bytes=0')
if __name__=='__main__':main()
