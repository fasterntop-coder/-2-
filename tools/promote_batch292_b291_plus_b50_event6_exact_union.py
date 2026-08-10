#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
B50_MANIFEST_SHA='81de1f2b6fc74e611f5cedb4d69265c0447324e9cb305337f4d9018b4e5a3861'
PARENT_STATUS='PASS_BATCH291_B290_PLUS_R39_FONT2_EXACT_UNION'
SUCCESS='PASS_BATCH292_B291_PLUS_B50_EVENT6_EXACT_UNION'
FROZEN=[
('SAKURA2/EV03023.MES',249716,73215,'0ce63bbf60d4f5f8f5db5d4b17366ff48b3894312fc5a503c661dee415a385d0','809f6de8cb68cd58bef167a02d3016aafb0456e6292362a81a509665279de36e'),
('SAKURA2/EV03024.MES',249666,72715,'64304d13c7bc169ac465349ddc696dbe84244df48da4dc707163b96db0626c0f','3632edc1ae7f559e21698f02658692a8ede71ab7dda78275ab035fa23d47143a'),
('SAKURA2/EV03025.MES',249616,71971,'16f942f697e2cffb919196281a4421248d543ee65e6b305dc1025ab9d507e187','10b98f0ad45d59cd144db74092dd8fd475740756125827683aae196f22abb4b7'),
('SAKURA2/EV03051.MES',249766,72195,'52bb28e84601210e32c576ccb869aaf9de176e721f1a61bbc3513fa72aeaa4bd','9c5923fe9da46a624077a30027cd54954d00139075953f827c074dcb184ea7c1'),
('SAKURA2/EV03052.MES',250067,72823,'3a3abccf661f164ff226564bdd87de29735a46b89ad0200bc1e5c3eb45f2e7ca','70b219f0534de8980eda46b89beb729858ec67ed1b3e06db7e3e16dcfb9ba0b2'),
('SAKURA2/EV03053.MES',250183,72322,'a0c60cb97a6b5b1d6bd9725932e00d3e50a83980122acaa2ff43715ebfba28c0','a2410d5fb4eaa275b69b95392782aba2dc6ee20891e9a0a4cfb15697fa460e99')]

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
 def add_bytes(data):
  d=shab(data)
  if d in wanted and d not in found:
   p=tmp/f'{d}.payload'; p.write_bytes(data); found[d]=p
 def visit(p):
  if p.suffix.lower()=='.zip':
   try:
    with zipfile.ZipFile(p) as z:
     for n in z.infolist():
      if not n.is_dir(): add_bytes(z.read(n))
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
 ap=argparse.ArgumentParser(); ap.add_argument('--parent-bin',type=Path,required=True); ap.add_argument('--parent-report',type=Path,required=True)
 ap.add_argument('--batch50-manifest',type=Path,required=True); ap.add_argument('--payload-input',type=Path,action='append',required=True)
 ap.add_argument('--output-bin',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); a=ap.parse_args()
 if a.parent_bin.stat().st_size!=DISC_SIZE: raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin); pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha: raise SystemExit('FAIL Batch291 parent report/SHA binding')
 if shaf(a.batch50_manifest)!=B50_MANIFEST_SHA: raise SystemExit('FAIL Batch50 manifest SHA')
 m=json.loads(a.batch50_manifest.read_text(encoding='utf-8')); reps=m.get('replacement_files',[])
 got=[(x['iso_path'],int(x['lba']),int(x['size']),x['source_sha256'].lower(),x['replacement_sha256'].lower()) for x in reps]
 if got!=FROZEN: raise SystemExit('FAIL Batch50 manifest entries differ from frozen B292 table')
 parent=a.parent_bin.read_bytes(); out=bytearray(parent); expected={}
 wanted={x[4] for x in FROZEN}
 with tempfile.TemporaryDirectory(prefix='st2_b292_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td)); miss=wanted-set(payloads)
  if miss: raise SystemExit('FAIL missing payload SHA(s): '+','.join(sorted(miss)))
  audit=[]
  for path,lba,size,src_sha,dst_sha in FROZEN:
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
      expected[L]={'lba':L,'asset':path,'before_sha256':shab(before),'after_sha256':shab(after)}; out[off:off+RAW_SECTOR_SIZE]=after
     pos+=take; idx+=1
    state='promoted_from_exact_source'
   final=shab(extract(out,lba,size))
   if final!=dst_sha: raise SystemExit(f'FAIL re-extraction {path}')
   audit.append({'iso_path':path,'lba':lba,'size':size,'parent_asset_sha256':cur_sha,'final_asset_sha256':final,'state':state,'reextraction':'PASS'})
 actual=[]
 for L in range(DISC_SIZE//RAW_SECTOR_SIZE):
  o=L*RAW_SECTOR_SIZE
  if parent[o:o+RAW_SECTOR_SIZE]!=out[o:o+RAW_SECTOR_SIZE]: actual.append(L)
 if actual!=sorted(expected): raise SystemExit('FAIL changed-LBA accounting')
 for L in actual:
  o=L*RAW_SECTOR_SIZE; sec=bytes(out[o:o+RAW_SECTOR_SIZE]); rec=expected[L]
  if not verify_mode1_sector(sec)['valid'] or shab(parent[o:o+RAW_SECTOR_SIZE])!=rec['before_sha256'] or shab(sec)!=rec['after_sha256']: raise SystemExit(f'FAIL Expected Write/EDC/ECC LBA {L}')
 a.output_bin.parent.mkdir(parents=True,exist_ok=True); a.output_bin.write_bytes(out); output_sha=shaf(a.output_bin)
 rep={'batch':292,'status':SUCCESS,'parent_batch':291,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'legacy_manifest_sha256':B50_MANIFEST_SHA,'replacement_assets':6,'asset_reextraction':'6/6 PASS','guessed_payload_bytes':0,'expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS); print('output_sha256='+output_sha); print('event_assets=6/6'); print(f'changed_raw_sectors={len(actual)}')
if __name__=='__main__': main()
