#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_STATUS='PASS_BATCH292_B291_PLUS_B50_EVENT6_EXACT_UNION'
SUCCESS='PASS_BATCH293_B292_PLUS_B56_60_STORY5_EXACT_UNION'
MANIFEST_SHA={
 56:'6d069fb97d522f88fd909b8943947e31e99091e6cb196b84dd29ea69ce024996',
 57:'b72bcb9d629d1e34296f6a31f73ade73a391607d2cca28d1b2dbf9fe641e4658',
 58:'e1a4c4289b54e571a0381a11e54661120257a9caa994fbb15622e3a7d9b4f5bc',
 59:'62b34866a79f4058b6f08ab6d749e056bd45b75c3ec8652a50ffa5c113c582c3',
 60:'17849c8feb64af4486f1f9aefcaef0a2f3113ba700f510af1a2ad33923f0b86a'}
FROZEN=[
(56,'SAKURA1/SK0404.BIN',45682,44804,'4deb61ff0b8f25ad8494e6753af9b415f6f4351374f39704112574a793f2a710','7fd50fb8a2b236091b41c5a7b6ff7dc46c992e01790a5d534491649d64d830e5'),
(57,'SAKURA1/SK0503.BIN',45878,97324,'4187d409d38e268233a092d33c93490ae6f73080ef2c9c8eed916775cf5a8aca','c844f857de7260e0b2746d7702460709393d8b08821986129cc5e09de103e76b'),
(58,'SAKURA1/SK0502.BIN',45825,107920,'8fb80c1353d9ceef632fc7198cf8e8ef045f41f08adcc43dbf7cbb9262273ea4','0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc'),
(59,'SAKURA1/SK0504.BIN',45926,127140,'52d5429c1d0e4029406d63f9b780bda3d78bb3de90233d4e5de488d2713d07bb','619bee36d6e821665df9e09a0b0ffa36021b58fdbda0c3fbf0f81a9e7421f4ac'),
(60,'SAKURA1/SK0501.BIN',45704,246748,'8ba6f9332c7dd84b39aa72cb20b98df417d1395db2ec696fd95a9824d879544f','6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743')]

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
 if len(a.legacy_manifest)!=5: raise SystemExit('FAIL require exactly five legacy manifests')
 if a.parent_bin.stat().st_size!=DISC_SIZE: raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin); pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha: raise SystemExit('FAIL Batch292 parent report/SHA binding')
 frozen_by_batch={x[0]:x for x in FROZEN}; seen=set()
 for p in a.legacy_manifest:
  h=shaf(p); batch=next((b for b,s in MANIFEST_SHA.items() if s==h),None)
  if batch is None or batch in seen: raise SystemExit(f'FAIL unknown/duplicate legacy manifest {p}')
  seen.add(batch); m=json.loads(p.read_text(encoding='utf-8')); r=m.get('replacement')
  if not isinstance(r,dict): raise SystemExit(f'FAIL legacy manifest schema batch {batch}')
  f=frozen_by_batch[batch]
  got=(batch,r['iso_path'],int(r['lba']),int(r['size']),r['source_sha256'].lower(),r['replacement_sha256'].lower())
  if got!=f: raise SystemExit(f'FAIL frozen legacy manifest mismatch batch {batch}')
 if seen!=set(MANIFEST_SHA): raise SystemExit('FAIL missing legacy manifest batch')
 parent=a.parent_bin.read_bytes(); out=bytearray(parent); expected={}; wanted={x[5] for x in FROZEN}
 with tempfile.TemporaryDirectory(prefix='st2_b293_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td)); miss=wanted-set(payloads)
  if miss: raise SystemExit('FAIL missing payload SHA(s): '+','.join(sorted(miss)))
  audit=[]
  for batch,path,lba,size,src_sha,dst_sha in FROZEN:
   cur=extract(out,lba,size); cur_sha=shab(cur)
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
 rep={'batch':293,'status':SUCCESS,'parent_batch':292,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'legacy_manifest_sha256':MANIFEST_SHA,'replacement_assets':5,'asset_reextraction':'5/5 PASS','guessed_payload_bytes':0,'expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS); print('output_sha256='+output_sha); print('story_assets=5/5'); print(f'changed_raw_sectors={len(actual)}')
if __name__=='__main__': main()
