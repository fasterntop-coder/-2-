#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_STATUS='PASS_BATCH294_B293_PLUS_B61_62_STORY_FINAL5_EXACT_UNION'
SUCCESS='PASS_BATCH295_B294_PLUS_B55_EVENT15_EXACT_UNION'
MANIFEST_SHA='db9329bffed005551f9ae3f8cf593c9019c7f75483318f5a2efe8c24332f4db5'
FROZEN=[
('SAKURA2/EV33001.MES',251253,73762,'1bcf6111786c3ca1f79549630913d4a240c24824276fc89e9c5cbff8dfbfb11f','95faefe8938cc5168da02c596d7faae65dabc1263064c10e8b0052de860be53c'),
('SAKURA2/EV33002.MES',251202,72858,'ebc7ae155c22ab38c24c87f3cf8eb2b5b145bcdc8c185efcd857b1320fc61687','5eda0cdc1e1f9989f1d96463fa4e489f388f2da8a0af87e90dc40c74753fab3b'),
('SAKURA2/EV33054.MES',251373,72514,'2defc26a1695d72506b7cb836d3866f960678b798e542fe345594457f350d0c0','7d35fb633f846d39a39d16baa8436be78ab290c6c8a430efd3661239a61f3280'),
('SAKURA2/EV34001.MES',252495,71974,'b1a61046e6439704408313fa86499bc612bab55861bfcc30254fcc52abeef1a1','6fb11f7058528e25398fad4ad9e6b569ffda12da3bd655e03c4e7c976682aca1'),
('SAKURA2/EV34002.MES',252546,73340,'2c5728db2cbbca8f00b61493f2049f5cf67c72dabe545197583d0e53e03af807','7321013e142a9533983d94e66b0fe491e86b97f099504dddb51f8f56793c9a06'),
('SAKURA2/EV34003.MES',252598,73185,'f794a556b172387bacda23ddb0d758ac1c8c61190725a970c3a974f01f7dd374','d5d1d116b7cfcf0e105a6ea71ab4cc4d4a7e41bb022d0f7419c4d31c4ef6cc9c'),
('SAKURA2/EV34004.MES',253078,72197,'ec7894f15c03e32b31f25a2f87f251538ba4fecf36c68a7ca5fd462218879ac0','9d86c56e0e605aa4a5af7ca179d130a8a3ffb618edad1e46a6fe79684ac37bc4'),
('SAKURA2/EV34006.MES',252649,72506,'4e2b1481fbc35147ce9cacf1eb3d5eff0befaad74b9767234a980bd36968b50d','68120a6fa055e94bf4b6dac34f6100ac9a85519766482c964a893b2575dd2f59'),
('SAKURA2/EV34007.MES',252699,72027,'c397ecdbc3a9ef260cb90550a5d43c7f3deb4cb8f05f6df3ea49e03ec47f7720','876843bdaf0a027e27d989321773531f871d03db7fe3d8c46a47a1439abaab7b'),
('SAKURA2/EV34008.MES',252750,72037,'35759b9871dcfda4ed53dc7e438f1aec76e62b4ce788114aa95676efaad9febe','0dd3612ca4f9a69134f2b68e56c54a7a7e3ac4b1d2d56d436674bd54853c8dae'),
('SAKURA2/EV34040.MES',252814,72181,'798b172e04d01084f031e4833d93c2479f2b229a87de634d787f5d015f673fd6','8371904e6790f5a7a80820cc240123ac86e36d97bac3ed17d2d493885ea26ffe'),
('SAKURA2/EV34041.MES',252864,71910,'c60df302679ed49529c2c48f333d1f2566b830db3cfe74e446be71e9f6ef5b85','b053b69e6f23605354920dd549117dc79abeb82617806e4083ec2bc392ac12bc'),
('SAKURA2/EV34042.MES',252914,71994,'5a35a527cb0ecbf0a63307dda020a35b641f0e0a2224bcb713175da30a0537bb','6ac577603d30f0082994c83f8d4c5a58c94b5df5a23d6184301fd588dd46f9be'),
('SAKURA2/EV34043.MES',252964,71941,'55631e480500fbdc5919da2959bd3ad9cc696248fb11c52ff8c28cd16531139f','7538b05adabb9b500d1bf8b7d6674860be20d3b92f437bf43e5e1f3ad63f1b13'),
('SAKURA2/EV34044.MES',253014,71923,'0bb80fe4c4db3dd4b4670d77e1a0971a3d141f717060c78e8f5f5cd91ac93df6','060fc543c74522514857453213116ba1470fec9d2230212bf484b7ea3897755d')]

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
 ap.add_argument('--legacy-manifest',type=Path,required=True); ap.add_argument('--payload-input',type=Path,action='append',required=True)
 ap.add_argument('--output-bin',type=Path,required=True); ap.add_argument('--report',type=Path,required=True); a=ap.parse_args()
 if a.parent_bin.stat().st_size!=DISC_SIZE: raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin); pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha: raise SystemExit('FAIL Batch294 parent report/SHA binding')
 if shaf(a.legacy_manifest)!=MANIFEST_SHA: raise SystemExit('FAIL Batch55 legacy manifest SHA')
 m=json.loads(a.legacy_manifest.read_text(encoding='utf-8')); rows=m.get('replacement_files')
 if not isinstance(rows,list): raise SystemExit('FAIL Batch55 legacy manifest schema')
 got={(r['iso_path'],int(r['lba']),int(r['size']),r['source_sha256'].lower(),r['replacement_sha256'].lower()) for r in rows}
 if got!=set(FROZEN): raise SystemExit('FAIL frozen Batch55 manifest mismatch')
 parent=a.parent_bin.read_bytes(); out=bytearray(parent); expected={}; wanted={x[4] for x in FROZEN}
 with tempfile.TemporaryDirectory(prefix='st2_b295_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td)); miss=wanted-set(payloads)
  if miss: raise SystemExit('FAIL missing payload SHA(s): '+','.join(sorted(miss)))
  audit=[]
  for path,lba,size,src_sha,dst_sha in FROZEN:
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
 rep={'batch':295,'status':SUCCESS,'parent_batch':294,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'legacy_manifest_sha256':MANIFEST_SHA,'replacement_assets':15,'batch55_records_reviewed':175,'batch55_records_translated':175,'event_mes_completion_files':'109/109','event_mes_completion_records':'1094/1094','asset_reextraction':'15/15 PASS','guessed_payload_bytes':0,'expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS); print('output_sha256='+output_sha); print('batch55_event_assets=15/15'); print('event_mes_static_completion=109/109 files, 1094/1094 records'); print(f'changed_raw_sectors={len(actual)}')
if __name__=='__main__': main()
