#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct, zlib
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector
MAGIC=b'ST2SP314'; VERSION=1; HEADER_FMT='>8sIIQI32s32s'; HEADER_SIZE=struct.calcsize(HEADER_FMT)
DISC_SIZE=659_293_824; TOTAL_SECTORS=DISC_SIZE//RAW_SECTOR_SIZE
PRISTINE_SHA256='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
CANDIDATE_SHA256='8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01'
EXPECTED_CHANGED=90_272; EXPECTED_UNCHANGED=TOTAL_SECTORS-EXPECTED_CHANGED
PASS='PASS_B323_FULL_DISC_SECTOR_ACCOUNTING_AND_MATERIALIZATION'
def die(m): raise SystemExit('FAIL '+m)
def sha_file(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''): h.update(c)
 return h.hexdigest()
def load_patch(p):
 changed={}; chain=hashlib.sha256(); edc_bad=[]
 with p.open('rb') as f:
  h=f.read(HEADER_SIZE)
  if len(h)!=HEADER_SIZE: die('truncated patch header')
  magic,ver,ss,fs,count,pristine,candidate=struct.unpack(HEADER_FMT,h)
  if (magic,ver,ss,fs,count)!=(MAGIC,VERSION,RAW_SECTOR_SIZE,DISC_SIZE,EXPECTED_CHANGED): die('patch header/geometry mismatch')
  if pristine.hex()!=PRISTINE_SHA256 or candidate.hex()!=CANDIDATE_SHA256: die('patch lineage mismatch')
  prev=-1
  for i in range(count):
   r=f.read(8)
   if len(r)!=8: die(f'truncated record {i}')
   lba,clen=struct.unpack('>II',r)
   if lba<=prev or lba>=TOTAL_SECTORS: die(f'invalid/duplicate LBA {lba}')
   payload=f.read(clen)
   if len(payload)!=clen: die(f'truncated payload LBA {lba}')
   try: raw=zlib.decompress(payload)
   except zlib.error as e: die(f'zlib LBA {lba}: {e}')
   if len(raw)!=RAW_SECTOR_SIZE: die(f'bad sector size LBA {lba}')
   v=verify_mode1_sector(raw)
   if not v.get('valid'): edc_bad.append(lba)
   changed[lba]=raw; chain.update(struct.pack('>I',lba)); chain.update(hashlib.sha256(raw).digest()); prev=lba
  if f.read(1): die('trailing patch bytes')
 if len(changed)!=EXPECTED_CHANGED: die('changed count mismatch')
 if edc_bad: die(f'EDC/ECC failures {len(edc_bad)} examples={edc_bad[:16]}')
 return changed,chain.hexdigest()
def main():
 ap=argparse.ArgumentParser(description='Batch323: materialize authoritative Disc1 candidate while proving complete 280,312-sector accounting: 90,272 changed, 190,040 unchanged byte-identical, and MODE1/2352 EDC/ECC valid on every changed sector.')
 ap.add_argument('--pristine-bin',type=Path,required=True); ap.add_argument('--patch-file',type=Path,required=True); ap.add_argument('--output-bin',type=Path,required=True); ap.add_argument('--report',type=Path,required=True)
 a=ap.parse_args()
 for p in (a.pristine_bin,a.patch_file):
  if not p.is_file(): die(f'missing input {p}')
 if a.output_bin.exists() or a.report.exists(): die('refusing to overwrite output')
 if a.pristine_bin.stat().st_size!=DISC_SIZE or sha_file(a.pristine_bin)!=PRISTINE_SHA256: die('pristine size/SHA mismatch')
 changed,chain=load_patch(a.patch_file)
 a.output_bin.parent.mkdir(parents=True,exist_ok=True); h=hashlib.sha256(); changed_seen=unchanged_seen=0; unchanged_chain=hashlib.sha256()
 try:
  with a.pristine_bin.open('rb') as src,a.output_bin.open('wb') as out:
   for lba in range(TOTAL_SECTORS):
    orig=src.read(RAW_SECTOR_SIZE)
    if len(orig)!=RAW_SECTOR_SIZE: die(f'short pristine read LBA {lba}')
    repl=changed.get(lba)
    if repl is None:
     out.write(orig); h.update(orig); unchanged_chain.update(struct.pack('>I',lba)); unchanged_chain.update(hashlib.sha256(orig).digest()); unchanged_seen+=1
    else:
     if repl==orig: die(f'changed LBA identical to pristine {lba}')
     out.write(repl); h.update(repl); changed_seen+=1
   if src.read(1): die('unexpected pristine trailing byte')
  digest=h.hexdigest()
  if changed_seen!=EXPECTED_CHANGED or unchanged_seen!=EXPECTED_UNCHANGED or changed_seen+unchanged_seen!=TOTAL_SECTORS: die('full-disc sector accounting mismatch')
  if digest!=CANDIDATE_SHA256: die(f'candidate SHA mismatch {digest}')
 except BaseException:
  if a.output_bin.exists(): a.output_bin.unlink()
  raise
 report={'batch':323,'status':PASS,'goal':'CD1_100_PERCENT_CANDIDATE','lineage':{'pristine_sha256':PRISTINE_SHA256,'candidate_sha256':CANDIDATE_SHA256,'sparse_patch_batch':314,'estimated_or_guessed_bytes':0},'disc_geometry':{'bytes':DISC_SIZE,'raw_sector_bytes':RAW_SECTOR_SIZE,'total_sectors':TOTAL_SECTORS},'accounting':{'changed_sectors':changed_seen,'expected_changed':EXPECTED_CHANGED,'unchanged_sectors':unchanged_seen,'expected_unchanged':EXPECTED_UNCHANGED,'accounted_sectors':changed_seen+unchanged_seen,'unaccounted_sectors':0},'gates':{'pristine_full_sha256':'PASS','patch_lineage':'PASS','changed_sector_edc_ecc':f'{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS','changed_sector_not_identical_to_pristine':f'{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS','unchanged_sector_byte_identity':f'{EXPECTED_UNCHANGED}/{EXPECTED_UNCHANGED} PASS','full_disc_sector_accounting':f'{TOTAL_SECTORS}/{TOTAL_SECTORS} PASS','candidate_full_sha256':'PASS','estimated_or_guessed_bytes':0},'chains':{'changed_lba_sector_chain_sha256':chain,'unchanged_lba_sector_chain_sha256':unchanged_chain.hexdigest()},'output':{'bin':a.output_bin.name,'sha256':digest,'size':a.output_bin.stat().st_size},'hardware_validation':'PENDING; byte, sector-accounting and MODE1 integrity gate only'}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(PASS); print(f'full_disc_sector_accounting={TOTAL_SECTORS}/{TOTAL_SECTORS} PASS'); print(f'changed={changed_seen} unchanged={unchanged_seen} unaccounted=0'); print(f'candidate_sha256={digest}'); print('estimated_or_guessed_bytes=0')
if __name__=='__main__': main()
