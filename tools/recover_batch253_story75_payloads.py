#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, json, zipfile

RAW=2352; USER_OFF=16; USER=2048
PRISTINE='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
NAMES=[f'BATCH{i}_PATCH_MANIFEST.json' for i in range(50,56)]
COUNTS=[6,9,18,19,8,15]

def sha(b): return hashlib.sha256(b).hexdigest()
def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024): h.update(c)
 return h.hexdigest()

def load(d):
 out={}
 for n,c in zip(NAMES,COUNTS):
  p=d/n; o=json.loads(p.read_text(encoding='utf-8'))
  if o.get('target_disc')!=1 or o.get('parent_bin_sha256')!=PRISTINE: raise SystemExit(f'bad lineage {n}')
  xs=o.get('replacement_files',[])
  if len(xs)!=c: raise SystemExit(f'bad count {n}')
  for x in xs: out[Path(x['iso_path']).name]=x
 if len(out)!=75: raise SystemExit('story75 cardinality failure')
 return out

def extract(f,lba,size):
 out=bytearray(); r=size
 while r:
  f.seek(lba*RAW); s=f.read(RAW)
  if len(s)!=RAW or s[15]!=1: raise ValueError('not MODE1/2352')
  n=min(USER,r); out+=s[USER_OFF:USER_OFF+n]; r-=n; lba+=1
 return bytes(out)

def save(name,data,row,out,found,source):
 if len(data)!=row['size'] or sha(data)!=row['replacement_sha256']: return False
 out.mkdir(parents=True,exist_ok=True); p=out/name
 if not p.exists(): p.write_bytes(data)
 if shaf(p)!=row['replacement_sha256']: raise ValueError(f'output conflict {name}')
 found[name]={'sha256':row['replacement_sha256'],'source':source}; return True

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--manifest-dir',type=Path,required=True); ap.add_argument('--root',type=Path,required=True); ap.add_argument('--out',type=Path,default=Path('BATCH253_STORY75_PAYLOADS')); ap.add_argument('--result',type=Path,default=Path('BATCH253_RESULT.json')); a=ap.parse_args()
 exp=load(a.manifest_dir); found={}; bins=[]; zips=[]
 for p in a.root.rglob('*.MES'):
  if p.name in exp: save(p.name,p.read_bytes(),exp[p.name],a.out,found,f'loose:{p}')
 for p in a.root.rglob('*.bin'):
  if len(found)==75: break
  if p.stat().st_size!=659293824: continue
  m=0
  with p.open('rb') as f:
   for n,row in exp.items():
    if n in found: continue
    try: data=extract(f,row['lba'],row['size'])
    except ValueError: break
    if save(n,data,row,a.out,found,f'bin:{p}'): m+=1
  bins.append({'path':str(p),'sha256':shaf(p),'matched':m})
 for p in a.root.rglob('*.zip'):
  if len(found)==75: break
  m=0
  try:
   with zipfile.ZipFile(p) as z:
    for i in z.infolist():
     n=Path(i.filename).name
     if n in exp and n not in found and save(n,z.read(i),exp[n],a.out,found,f'zip:{p}!{i.filename}'): m+=1
  except zipfile.BadZipFile: pass
  zips.append({'path':str(p),'matched':m})
 missing=sorted(set(exp)-set(found)); status='PASS_STORY75_75_OF_75' if not missing else 'PARTIAL_EXACT_RECOVERY'
 r={'batch':253,'status':status,'expected':75,'recovered':len(found),'missing':missing,'found':found,'bins':bins,'zips':zips,'guessed_bytes':False,'next':'feed output directory to Story75/Story109 integrators'}
 a.result.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'status':status,'recovered':len(found),'missing':len(missing)})); return 0 if not missing else 2
if __name__=='__main__': raise SystemExit(main())
