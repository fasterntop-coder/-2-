#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, json, shutil

def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024): h.update(c)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser(description='Assemble exact 107-file Story109 candidate directory from multiple recovery roots')
 ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
 ap.add_argument('--root',type=Path,action='append',required=True)
 ap.add_argument('--out',type=Path,default=Path('BATCH254_STORY109_CANDIDATES'))
 ap.add_argument('--result',type=Path,default=Path('BATCH254_STORY109_ASSEMBLY_RESULT.json'))
 a=ap.parse_args(); m=json.loads(a.manifest.read_text(encoding='utf-8')); xs=m.get('replacement_files',[])
 if m.get('format')!='ST2-CD1-BATCH253-STORY109-PROMOTION-v1' or len(xs)!=107: raise SystemExit('Story109 promotion manifest gate failed')
 expected={Path(x['iso_path']).name:x for x in xs}; found={}; conflicts=[]
 for root in a.root:
  if not root.exists(): continue
  paths=[root] if root.is_file() else root.rglob('*.MES')
  for p in paths:
   if not p.is_file() or p.name not in expected: continue
   row=expected[p.name]
   if p.stat().st_size!=row['size']: continue
   got=shaf(p)
   if got!=row['replacement_sha256']: continue
   old=found.get(p.name)
   if old and old['sha256']!=got: conflicts.append({'file':p.name,'a':old['path'],'b':str(p)}); continue
   found[p.name]={'path':str(p),'sha256':got}
 a.out.mkdir(parents=True,exist_ok=True)
 for name,v in found.items():
  dst=a.out/name
  if dst.exists() and shaf(dst)!=v['sha256']: raise SystemExit(f'output conflict {name}')
  if not dst.exists(): shutil.copyfile(v['path'],dst)
 verified=[]
 for name,row in expected.items():
  p=a.out/name
  if p.is_file() and p.stat().st_size==row['size'] and shaf(p)==row['replacement_sha256']: verified.append(name)
 missing=sorted(set(expected)-set(verified)); status='PASS_STORY109_107_OF_107_CANDIDATE_DIR' if not missing else 'PARTIAL_EXACT_ASSEMBLY'
 r={'batch':254,'status':status,'expected':107,'assembled':len(verified),'missing_count':len(missing),'missing_files':missing,'conflicts':conflicts,'guessed_bytes':False,'next':'run Story109 raw-sector integrator only when assembled=107'}
 a.result.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'status':status,'assembled':len(verified),'missing':len(missing)})); return 0 if not missing else 2
if __name__=='__main__': raise SystemExit(main())
