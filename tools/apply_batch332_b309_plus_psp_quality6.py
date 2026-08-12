#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json, shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE_NAME='apply_batch330_b309_plus_b329_quality_overlay.py'
base_path=HERE/BASE_NAME
if not base_path.exists():
    raise SystemExit(f'missing sibling tool: {base_path}')
spec=importlib.util.spec_from_file_location('b330',base_path)
b330=importlib.util.module_from_spec(spec);spec.loader.exec_module(b330)

EXPECTED_PARENT=b330.EXPECTED_PARENT
ASSETS=[
 {"path":"SAKURA2/EV00060.MES","lba":247407,"size":72656,"source_sha256":"f26295cffa37706af3792d194c39384e634565029ab2e0c5348153a8966c641d","replacement_sha256":"8d6b79d3b120d0af68437c5a5fe9834aae66a5bcfacee3f7b6cb005a092f2fbd"},
 {"path":"SAKURA2/EV00002.MES","lba":247457,"size":71798,"source_sha256":"07e4f2272b0cc5755f89e1b1c50bb641ac9da8e0c600ca8d8a989f8f392c5708","replacement_sha256":"5e82fa4fca18eb189b8cf2b6eb6fd80faf79053ddfc735a373d1067894e74752"},
 {"path":"SAKURA2/EV03021.MES","lba":249816,"size":73972,"source_sha256":"936ff18bfb18487a85eaded8dd892ed23c421d19a5c600192b3c6c10101d2786","replacement_sha256":"83d572e8e3dee0bb18239f082359df4a683c7e1803bf29dab5ea131b59cbc561"},
 {"path":"SAKURA2/EV04001.MES","lba":250542,"size":73191,"source_sha256":"d39b5c7559e93802eb61af162a48a0e9328acb2a0b04a3cf87107ea53f77566f","replacement_sha256":"c130c1d6719e338c5dc787788923b95185c2886ae4f36c0bbb93a365a648a9f7"},
 {"path":"SAKURA2/EV32001.MES","lba":250584,"size":73191,"source_sha256":"472c18655cd5f009aeaf1986eb24f59f6f4f77cd77683e58274b61b4927f3ee7","replacement_sha256":"e8586d4eb1f499447367c540260fe83e7747cf3cdfdfd31e4620afe299fe67e6"},
 {"path":"SAKURA2/EV33001.MES","lba":251253,"size":73762,"source_sha256":"95faefe8938cc5168da02c596d7faae65dabc1263064c10e8b0052de860be53c","replacement_sha256":"e724f8365784228a833625e8a99632a6ae67491bc22df20cffd0de45a4979651"},
]

def sha_file(path:Path)->str:return b330.sha_file(path)
def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def main()->int:
 ap=argparse.ArgumentParser(description='Materialize Batch332: exact Batch309 parent plus six PSP-guided quality replacement MES assets')
 ap.add_argument('parent_bin',type=Path)
 ap.add_argument('batch329_dir',type=Path)
 ap.add_argument('batch331_dir',type=Path)
 ap.add_argument('output_bin',type=Path)
 ap.add_argument('--expected-parent-sha256',default=EXPECTED_PARENT)
 ap.add_argument('--report',type=Path)
 args=ap.parse_args()
 parent_sha=sha_file(args.parent_bin)
 if parent_sha.lower()!=args.expected_parent_sha256.lower():raise SystemExit(f'parent SHA mismatch: {parent_sha}')
 def replacement_path(asset):
  root=args.batch329_dir if Path(asset['path']).name in {'EV00002.MES','EV00060.MES'} else args.batch331_dir
  return root/asset['path']
 with args.parent_bin.open('rb') as f:
  for a in ASSETS:
   current=b330.extract_asset(f,int(a['lba']),int(a['size']))
   if sha(current)!=a['source_sha256']:raise SystemExit(f"parent asset mismatch: {a['path']} {sha(current)}")
   repl=replacement_path(a).read_bytes()
   if len(repl)!=a['size'] or sha(repl)!=a['replacement_sha256']:raise SystemExit(f"replacement mismatch: {a['path']}")
 args.output_bin.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(args.parent_bin,args.output_bin)
 changed=[]
 with args.output_bin.open('r+b') as f:
  for a in ASSETS:
   changed.extend(b330.patch_asset(f,int(a['lba']),replacement_path(a).read_bytes()))
  for a in ASSETS:
   got=b330.extract_asset(f,int(a['lba']),int(a['size']))
   if sha(got)!=a['replacement_sha256']:raise SystemExit(f"post-write re-extraction mismatch: {a['path']}")
 changed=sorted(set(changed));output_sha=sha_file(args.output_bin)
 report={"format":"ST2-CD1-BATCH332-B309-PLUS-PSP-QUALITY6-v1","batch":332,"status":"PASS_MATERIALIZED_CHILD_CANDIDATE","parent_sha256":parent_sha,"output_sha256":output_sha,"replacement_files":6,"corrected_records":7,"changed_raw_sectors_vs_parent":len(changed),"changed_lbas_vs_parent":changed,"all_written_sectors_mode1_edc_ecc":True,"asset_reextraction":"6/6 PASS","guessed_bytes":0,"assets":ASSETS}
 rp=args.report or args.output_bin.with_suffix(args.output_bin.suffix+'.batch332.json');rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
