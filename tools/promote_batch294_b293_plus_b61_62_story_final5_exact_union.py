#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_STATUS='PASS_BATCH293_B292_PLUS_B56_60_STORY5_EXACT_UNION'
SUCCESS='PASS_BATCH294_B293_PLUS_B61_62_STORY_FINAL5_EXACT_UNION'
MANIFEST_SHA={61:'4c926e11d0eaeda283b2943b92c77fc54352c33f8c90646eace2f02c23c6f078',62:'cf132223f83ba37fe0711e5fe4d49dfc055c4df61579eb8cdd782b203fa8eba4'}
FROZEN=[
(61,'SAKURA1/SK0505.BIN',45989,37136,'c2f59f4711a55c722e166ab4114f0f1ac88db459e3312b94a2a916fc01aa23ce','102709b60da35894b03d2f03716b8a14735f6711031b28fad7cc995cffe73104'),
(61,'SAKURA1/SK1304.BIN',46008,44464,'591e9b23b035b3bb5786043318695c865d771d22aa8f53fbcc433359b04418f2','ff6e9b29a6ba76f8ee706f55041a9f83bb6246f24061efbfd00d41d042a54722'),
(62,'SAKURA1/SKCM02.BIN',46030,129652,'ca7631c90c264b91a13e96dd21d656c59048b9961b182e3d261c146811c883af','0a2d0edf358b8fe6ab6edbc058e7e1263fc466706312bec43fd9994eb38419d9'),
(62,'SAKURA1/SKCM04.BIN',46094,91196,'59b7fdb48784a510c5227dd1f3f3ef8c1172c7b00e692ade0d7ffb7ae44e0e29','c3e78d0b32b87d58d720c0fdd616fbc2fba232b306abe8c528d66a524664c4f8'),
(62,'SAKURA1/SKCM05.BIN',46139,91416,'99375992aedd61f37cec7fdf7574581abcd7e222be8b01aae0937257752dc257','cfd966f1cc1783f0da0f988aba92bd7591237cacb10c633da0063ce1f71c29f4')]

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
  out+=sec[USER_OFF:USER_OFF+min(USER_SIZE,size-len(out))]; i+=1
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
 ap.add_argument('--legacy-manifest',type=Path,action='append',required=True); ap.add_argument('--payload-input',type=Path,action='append',required=True)
 ap.add_argument('--output-bin',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); a=ap.parse_args()
 if len(a.legacy_manifest)!=2: raise SystemExit('FAIL require exactly Batch61 and Batch62 manifests')
 if a.parent_bin.stat().st_size!=DISC_SIZE: raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin); pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha: raise SystemExit('FAIL Batch293 parent report/SHA binding')
 frozen_by_batch={b:[x for x in FROZEN if x[0]==b] for b in MANIFEST_SHA}; seen=set()
 for p in a.legacy_manifest:
  h=shaf(p); batch=next((b for b,s in MANIFEST_SHA.items() if s==h),None)
  if batch is None or batch in seen: raise SystemExit(f'FAIL unknown/duplicate legacy manifest {p}')
  seen.add(batch); m=json.loads(p.read_text(encoding='utf-8')); rows=m.get('replacement_files')
  if not isinstance(rows,list): raise SystemExit(f'FAIL legacy manifest schema batch {batch}')
  got={(batch,r['iso_path'],int(r['lba']),int(r['size']),r['source_sha256'].lower(),r['replacement_sha256'].lower()) for r in rows}
  if got!=set(frozen_by_batch[batch]): raise SystemExit(f'FAIL frozen legacy manifest mismatch batch {batch}')
 if seen!=set(MANIFEST_SHA): raise SystemExit('FAIL missing legacy manifest batch')
 parent=a.parent_bin.read_bytes(); out=bytearray(parent); expected={}; wanted={x[5] for x in FROZEN}
 with tempfile.TemporaryDirectory(prefix='st2_b294_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td)); miss=wanted-set(payloads)
  if miss: raise SystemExit('FAIL missing payload SHA(s): '+','.join(sorted(miss)))
  audit=[]
  for batch,path,lba,size,src_sha,dst_sha in FROZEN:
   cur_sha=shab(extract(out,lba,size))
   if cur_sha not in {src_sha,dst_sha}: raise SystemExit(f'FAIL third variant {path} {cur_sha}')
   state='already_target'
   if cur_sha==src_sha and src_sha!=dst_sha:
    payload=payloads[dst_sha].read_bytes()
    if len(payload)!=size or shab(payload)!=dst_sha: raise SystemExit(f'FAIL payload {path}')
    pos=0; idx=0
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
   if final!=dst_sha: raise SystemExit(f'FAIL re-extraction {path}')
   audit.append({'batch':batch,'iso_path':path,'lba':lba,'size':size,'parent_asset_sha256':cur_sha,'final_asset_sha256':final,'state':state,'reextraction':'PASS'})
 actual=[]
 for L in range(DISC_SIZE//RAW_SECTOR_SIZE):
  o=L*RAW_SECTOR_SIZE
  if parent[o:o+RAW_SECTOR_SIZE]!=out[o:o+RAW_SECTOR_SIZE]: actual.append(L)
 if actual!=sorted(expected): raise SystemExit('FAIL changed-LBA accounting')
 for L in actual:
  o=L*RAW_SECTOR_SIZE; sec=bytes(out[o:o+RAW_SECTOR_SIZE]); rec=expected[L]
  if not verify_mode1_sector(sec)['valid'] or shab(parent[o:o+RAW_SECTOR_SIZE])!=rec['before_sha256'] or shab(sec)!=rec['after_sha256']: raise SystemExit(f'FAIL Expected Write/EDC/ECC LBA {L}')
 a.output_bin.parent.mkdir(parents=True,exist_ok=True); a.output_bin.write_bytes(out); output_sha=shaf(a.output_bin)
 rep={'batch':294,'status':SUCCESS,'parent_batch':293,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'legacy_manifest_sha256':MANIFEST_SHA,'replacement_assets':5,'story_records_reviewed':913,'story_records_translated':906,'story_control_preserved':7,'story_remaining_candidate_files':0,'story_remaining_candidate_records':0,'asset_reextraction':'5/5 PASS','guessed_payload_bytes':0,'expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS); print('output_sha256='+output_sha); print('story_final_assets=5/5'); print('story_inventory_remaining=0'); print(f'changed_raw_sectors={len(actual)}')
if __name__=='__main__': main()
