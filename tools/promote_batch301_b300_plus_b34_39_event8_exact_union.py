#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_STATUS='PASS_BATCH300_B299_PLUS_B41_44_EVENT9_EXACT_UNION'
SUCCESS='PASS_BATCH301_B300_PLUS_B34_39_EVENT8_EXACT_UNION'
LOGICAL_ROWS_SHA='a07a86dcde896df03d5bed763f1dad70e76fc35851abddce1823a733d5ad424a'

def shab(b): return hashlib.sha256(b).hexdigest()
def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''): h.update(c)
 return h.hexdigest()

def extract(raw,lba,size):
 out=bytearray(); i=0
 while len(out)<size:
  off=(lba+i)*RAW_SECTOR_SIZE; sec=raw[off:off+RAW_SECTOR_SIZE]
  if len(sec)!=RAW_SECTOR_SIZE or sec[15]!=1: raise SystemExit(f'FAIL MODE1 LBA {lba+i}')
  take=min(USER_SIZE,size-len(out)); out+=sec[USER_OFF:USER_OFF+take]; i+=1
 return bytes(out)

def rebuild(sec):
 sec[0x810:0x814]=edc(bytes(sec[:0x810])).to_bytes(4,'little'); sec[0x814:0x81C]=bytes(8)
 sec[0x81C:0x8C8]=_ecc_compute(bytes(sec[0x0C:0x81C]),86,24,2,86)
 sec[0x8C8:0x930]=_ecc_compute(bytes(sec[0x0C:0x8C8]),52,43,86,88)

def index_payloads(inputs,wanted,tmp):
 found={}
 def add(data):
  d=shab(data)
  if d in wanted and d not in found:
   q=tmp/f'{d}.payload'; q.write_bytes(data); found[d]=q
 def visit(p):
  if p.suffix.lower()=='.zip':
   try:
    with zipfile.ZipFile(p) as z:
     for n in z.infolist():
      if not n.is_dir(): add(z.read(n))
   except zipfile.BadZipFile: pass
  else:
   try:
    d=shaf(p)
    if d in wanted and d not in found: found[d]=p
   except OSError: pass
 for r in inputs:
  if r.is_dir():
   for p in r.rglob('*'):
    if p.is_file(): visit(p)
  elif r.is_file(): visit(r)
 return found

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--parent-bin',type=Path,required=True); ap.add_argument('--parent-report',type=Path,required=True)
 ap.add_argument('--union-manifest',type=Path,required=True); ap.add_argument('--payload-input',type=Path,action='append',required=True)
 ap.add_argument('--output-bin',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); a=ap.parse_args()
 if a.parent_bin.stat().st_size!=DISC_SIZE: raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin); pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha: raise SystemExit('FAIL Batch300 parent report/SHA binding')
 m=json.loads(a.union_manifest.read_text(encoding='utf-8')); manifest_sha=shaf(a.union_manifest); rows=m.get('replacement_files')
 if m.get('format')!='ST2-CD1-batch301-b300-plus-b34-39-event8-exact-union-v1': raise SystemExit('FAIL manifest format')
 if m.get('parent_batch')!=300 or m.get('replacement_assets')!=8: raise SystemExit('FAIL manifest header')
 if (m.get('records_reviewed'),m.get('records_translated'),m.get('control_preserved_records'))!=(119,116,3): raise SystemExit('FAIL frozen record totals')
 if m.get('guessed_payload_bytes')!=0 or not isinstance(rows,list) or len(rows)!=8: raise SystemExit('FAIL manifest policy/schema')
 logical=shab(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8'))
 if logical!=LOGICAL_ROWS_SHA or m.get('logical_rows_sha256')!=LOGICAL_ROWS_SHA: raise SystemExit('FAIL frozen logical rows SHA')
 if {int(r['source_batch']) for r in rows}!={34,35,36,37,38,39} or len({r['iso_path'] for r in rows})!=8: raise SystemExit('FAIL frozen asset set')
 parent=a.parent_bin.read_bytes(); out=bytearray(parent); expected={}; wanted={r['replacement_sha256'].lower() for r in rows}
 with tempfile.TemporaryDirectory(prefix='st2_b301_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td)); miss=wanted-set(payloads)
  if miss: raise SystemExit('FAIL missing payload SHA(s): '+','.join(sorted(miss)))
  audit=[]
  for r in rows:
   path=r['iso_path']; lba=int(r['lba']); size=int(r['size']); src=r['source_sha256'].lower(); dst=r['replacement_sha256'].lower()
   cur=shab(extract(out,lba,size))
   if cur not in {src,dst}: raise SystemExit(f'FAIL third variant {path} {cur}')
   state='already_target'
   if cur==src and src!=dst:
    payload=payloads[dst].read_bytes()
    if len(payload)!=size or shab(payload)!=dst: raise SystemExit(f'FAIL payload {path}')
    pos=idx=0
    while pos<size:
     L=lba+idx; off=L*RAW_SECTOR_SIZE; before=bytes(out[off:off+RAW_SECTOR_SIZE])
     if not verify_mode1_sector(before)['valid']: raise SystemExit(f'FAIL parent EDC/ECC LBA {L}')
     sec=bytearray(before); take=min(USER_SIZE,size-pos); sec[USER_OFF:USER_OFF+take]=payload[pos:pos+take]; rebuild(sec); after=bytes(sec)
     if before!=after:
      if not verify_mode1_sector(after)['valid']: raise SystemExit(f'FAIL rebuilt EDC/ECC LBA {L}')
      if L in expected and expected[L]['after_sha256']!=shab(after): raise SystemExit(f'FAIL LBA collision {L}')
      expected[L]={'lba':L,'asset':path,'before_sha256':shab(before),'after_sha256':shab(after)}; out[off:off+RAW_SECTOR_SIZE]=after
     pos+=take; idx+=1
    state='promoted_from_exact_source'
   final=shab(extract(out,lba,size))
   if final!=dst: raise SystemExit(f'FAIL re-extraction {path}')
   audit.append({'source_batch':int(r['source_batch']),'iso_path':path,'lba':lba,'size':size,'parent_asset_sha256':cur,'final_asset_sha256':final,'state':state,'reextraction':'PASS'})
 actual=[]
 for L in range(DISC_SIZE//RAW_SECTOR_SIZE):
  o=L*RAW_SECTOR_SIZE
  if parent[o:o+RAW_SECTOR_SIZE]!=out[o:o+RAW_SECTOR_SIZE]: actual.append(L)
 if actual!=sorted(expected): raise SystemExit('FAIL changed-LBA accounting')
 for L in actual:
  o=L*RAW_SECTOR_SIZE; sec=bytes(out[o:o+RAW_SECTOR_SIZE]); rec=expected[L]
  if not verify_mode1_sector(sec)['valid']: raise SystemExit(f'FAIL final EDC/ECC LBA {L}')
  if shab(parent[o:o+RAW_SECTOR_SIZE])!=rec['before_sha256'] or shab(sec)!=rec['after_sha256']: raise SystemExit(f'FAIL Expected Write LBA {L}')
 a.output_bin.parent.mkdir(parents=True,exist_ok=True); a.output_bin.write_bytes(out); output_sha=shaf(a.output_bin)
 rep={'batch':301,'status':SUCCESS,'parent_batch':300,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'union_manifest_sha256':manifest_sha,'logical_rows_sha256':LOGICAL_ROWS_SHA,'source_batches':[34,35,36,37,38,39],'replacement_assets':8,'records_reviewed':119,'records_translated':116,'control_preserved_records':3,'guessed_payload_bytes':0,'asset_reextraction':'8/8 PASS','expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS); print('output_sha256='+output_sha); print('event_assets=8/8'); print('records_reviewed=119 translated=116 control_preserved=3'); print(f'changed_raw_sectors={len(actual)}')
if __name__=='__main__': main()
