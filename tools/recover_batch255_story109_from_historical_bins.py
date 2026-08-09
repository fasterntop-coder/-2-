#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, tempfile, zipfile
from pathlib import Path

RAW=2352; USER_OFF=16; USER=2048
DISC_SIZE=659293824
SYNC=bytes([0]+[0xff]*10+[0])

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024):h.update(c)
 return h.hexdigest()

def extract_raw_bin(f,lba:int,size:int)->bytes:
 out=bytearray(); remain=size
 while remain:
  f.seek(lba*RAW); s=f.read(RAW)
  if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1: raise ValueError(f'not MODE1/2352 at LBA {lba}')
  n=min(USER,remain); out+=s[USER_OFF:USER_OFF+n]; remain-=n; lba+=1
 return bytes(out)

def scan_bin(path:Path, expected:dict[str,dict], found:dict, provenance:list):
 if path.stat().st_size!=DISC_SIZE:return
 matched=[]
 try:
  with path.open('rb') as f:
   for name,row in expected.items():
    if name in found:continue
    b=extract_raw_bin(f,row['lba'],row['size'])
    got=shab(b)
    if got==row['replacement_sha256']:
     matched.append((name,b,got))
 except Exception as e:
  provenance.append({'kind':'bin','path':str(path),'status':'REJECTED_RAW_FORMAT','error':str(e)[:240]});return
 for name,b,got in matched:found[name]={'bytes':b,'sha256':got,'source':str(path),'source_kind':'raw_bin'}
 provenance.append({'kind':'bin','path':str(path),'status':'SCANNED','matched_assets':len(matched)})

def scan_zip(path:Path,expected:dict[str,dict],found:dict,provenance:list,tmp:Path):
 try:
  with zipfile.ZipFile(path) as z:
   members=[i for i in z.infolist() if not i.is_dir() and i.file_size==DISC_SIZE and i.filename.lower().endswith(('.bin','.img','.raw'))]
   if not members:
    provenance.append({'kind':'zip','path':str(path),'status':'NO_FULL_RAW_BIN'});return
   total=0
   for i in members:
    target=tmp/(hashlib.sha256((str(path)+'|'+i.filename).encode()).hexdigest()+'.bin')
    with z.open(i) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst,8*1024*1024)
    before=len(found);scan_bin(target,expected,found,provenance);total+=len(found)-before;target.unlink(missing_ok=True)
   provenance.append({'kind':'zip','path':str(path),'status':'SCANNED_FULL_RAW_MEMBERS','raw_members':len(members),'new_assets':total})
 except (zipfile.BadZipFile,OSError) as e:provenance.append({'kind':'zip','path':str(path),'status':'REJECTED','error':str(e)[:240]})

def scan_loose_mes(root:Path,expected:dict[str,dict],found:dict,provenance:list):
 count=0
 for p in root.rglob('*.MES'):
  row=expected.get(p.name)
  if not row or p.name in found or p.stat().st_size!=row['size']:continue
  got=shaf(p)
  if got==row['replacement_sha256']:
   found[p.name]={'path':str(p),'sha256':got,'source':str(p),'source_kind':'loose_mes'};count+=1
 provenance.append({'kind':'loose_mes','path':str(root),'status':'SCANNED','new_assets':count})

def main()->int:
 ap=argparse.ArgumentParser(description='Batch255 recover all exact Story109 replacement payloads from historical raw BINs, ZIPs and loose MES files')
 ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
 ap.add_argument('--root',type=Path,action='append',required=True)
 ap.add_argument('--out',type=Path,default=Path('BATCH255_STORY109_RECOVERED'))
 ap.add_argument('--result',type=Path,default=Path('BATCH255_STORY109_RECOVERY_RESULT.json'))
 a=ap.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8'));xs=m.get('replacement_files',[])
 if m.get('format')!='ST2-CD1-BATCH253-STORY109-PROMOTION-v1' or len(xs)!=107:raise SystemExit('Story109 manifest/cardinality gate failed')
 expected={Path(x['iso_path']).name:x for x in xs}
 if len(expected)!=107:raise SystemExit('duplicate Story109 basenames')
 found={};prov=[];a.out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='st2_b255_') as td:
  tmp=Path(td)
  for root in a.root:
   if not root.exists():continue
   if root.is_dir():
    scan_loose_mes(root,expected,found,prov)
    bins=[p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in ('.bin','.img','.raw') and p.stat().st_size==DISC_SIZE]
    zips=[p for p in root.rglob('*.zip') if p.is_file()]
   else:
    bins=[root] if root.suffix.lower() in ('.bin','.img','.raw') and root.stat().st_size==DISC_SIZE else []
    zips=[root] if root.suffix.lower()=='.zip' else []
   for p in bins:scan_bin(p,expected,found,prov)
   for p in zips:
    if len(found)==107:break
    scan_zip(p,expected,found,prov,tmp)
 for name,v in found.items():
  dst=a.out/name
  if 'bytes' in v:
   data=v['bytes'];
   if shab(data)!=expected[name]['replacement_sha256']:raise SystemExit(f'internal byte gate failed: {name}')
   dst.write_bytes(data)
  else:shutil.copyfile(v['path'],dst)
 verified=[]
 for name,row in expected.items():
  p=a.out/name
  if p.is_file() and p.stat().st_size==row['size'] and shaf(p)==row['replacement_sha256']:verified.append(name)
 missing=sorted(set(expected)-set(verified));status='PASS_STORY109_107_OF_107_RECOVERED' if not missing else 'PARTIAL_EXACT_RECOVERY'
 result={'batch':255,'status':status,'expected_assets':107,'recovered_assets':len(verified),'missing_count':len(missing),'missing_files':missing,'provenance':prov,'safety':{'guessed_bytes':False,'replacement_sha256_required':True,'raw_lba_geometry_from_locked_manifest':True,'wrong_size_rejected':True},'next':'run tools/assemble_batch254_story109_candidate_dir.py then tools/integrate_batch253_story109.py only after 107/107'}
 a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':status,'recovered':len(verified),'missing':len(missing)},ensure_ascii=False));return 0 if not missing else 2
if __name__=='__main__':raise SystemExit(main())
