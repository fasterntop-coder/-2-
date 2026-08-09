#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent

def run(cmd:list[str],allow_partial=False)->int:
 print('+',' '.join(cmd),flush=True)
 p=subprocess.run(cmd,cwd=REPO)
 if p.returncode and not allow_partial:raise SystemExit(p.returncode)
 return p.returncode

def load(p:Path):return json.loads(p.read_text(encoding='utf-8'))

def main()->int:
 ap=argparse.ArgumentParser(description='Batch256 one-command exact Story109 recovery -> assembly -> physical integration pipeline')
 ap.add_argument('--root',type=Path,action='append',required=True,help='historical archive/BIN/MES search root; repeatable')
 ap.add_argument('--pristine',type=Path,required=True)
 ap.add_argument('--parent',type=Path,required=True,help='exact verified Batch247 parent')
 ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
 ap.add_argument('--work',type=Path,default=Path('BATCH256_STORY109_WORK'))
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B256_C2FIX_STATIC58_STORY109_KO.bin'))
 ap.add_argument('--result',type=Path,default=Path('BATCH256_STORY109_PIPELINE_RESULT.json'))
 a=ap.parse_args();a.work.mkdir(parents=True,exist_ok=True)
 recovered=a.work/'RECOVERED';recovery_result=a.work/'RECOVERY_RESULT.json';assembled=a.work/'ASSEMBLED';assembly_result=a.work/'ASSEMBLY_RESULT.json';integration_result=a.work/'INTEGRATION_RESULT.json'
 cmd=[sys.executable,str(HERE/'recover_batch255_story109_from_historical_bins.py'),'--manifest',str(a.manifest),'--out',str(recovered),'--result',str(recovery_result)]
 for r in a.root:cmd+=['--root',str(r)]
 run(cmd,allow_partial=True)
 rr=load(recovery_result)
 if rr.get('recovered_assets')!=107:
  result={'batch':256,'status':'BLOCKED_EXACT_PAYLOADS_INCOMPLETE','recovered_assets':rr.get('recovered_assets',0),'missing_count':rr.get('missing_count'),'missing_files':rr.get('missing_files',[]),'game_bytes_written':False,'guessed_bytes':False,'next':'add more historical roots and rerun same command'}
  a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 2
 run([sys.executable,str(HERE/'assemble_batch254_story109_candidate_dir.py'),'--manifest',str(a.manifest),'--root',str(recovered),'--out',str(assembled),'--result',str(assembly_result)])
 ar=load(assembly_result)
 if ar.get('assembled')!=107:raise SystemExit('assembly gate failed after 107/107 recovery')
 run([sys.executable,str(HERE/'integrate_batch253_story109.py'),'--manifest',str(a.manifest),'--pristine',str(a.pristine),'--parent',str(a.parent),'--candidate-dir',str(assembled),'--output',str(a.output),'--result',str(integration_result)])
 ir=load(integration_result)
 if ir.get('story_replacement_assets_promoted')!=107 or ir.get('story_control_assets_preserved')!=2 or ir.get('whole_asset_reextraction')!='107/107 PASS':raise SystemExit('integration completion gate failed')
 result={'batch':256,'status':'PASS_STORY109_ONE_COMMAND_EXECUTABLE_CANDIDATE','recovered_assets':107,'assembled_assets':107,'promoted_assets':107,'controls_preserved':2,'story_files_accounted':109,'output':str(a.output),'output_sha256':ir.get('output_sha256'),'changed_sectors':ir.get('changed_sectors'),'changed_sector_edc_ecc':ir.get('changed_sector_edc_ecc'),'whole_asset_reextraction':ir.get('whole_asset_reextraction'),'control_reextraction':ir.get('control_reextraction'),'expected_write_records':ir.get('expected_write_records'),'guessed_bytes':False}
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
