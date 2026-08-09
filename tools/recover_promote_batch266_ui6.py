#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil, tempfile, zipfile
from pathlib import Path
RAW=2352; USER_OFF=16; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
R37_SHA='56aa846382aae5e284c631d2814c1f7a45d84cb8dba8bc2e47ceff4f81733736'
R37_ZIP_SHA='ea088c6dbca381ba694442cb9bbb979f9ab3a43609565ab60849b7038bef4967'
DISC_SIZE=659293824

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024):h.update(c)
 return h.hexdigest()
def _edc_lut():
 out=[]
 for i in range(256):
  v=i
  for _ in range(8):v=(v>>1)^(0xD8018001 if v&1 else 0)
  out.append(v&0xffffffff)
 return out
EDC=_edc_lut()
def edc(d:bytes)->int:
 v=0
 for x in d:v=(v>>8)^EDC[(v^x)&255]
 return v&0xffffffff
def _ecc_luts():
 f=[0]*256;b=[0]*256
 for i in range(256):
  j=(i<<1)^(0x11D if i&0x80 else 0);f[i]=j&255;b[i^f[i]]=i
 return f,b
EF,EB=_ecc_luts()
def ecc(src:bytes,maj:int,minc:int,mult:int,inc:int)->bytes:
 size=maj*minc;o=bytearray(maj*2)
 for m in range(maj):
  idx=(m>>1)*mult+(m&1);a=b=0
  for _ in range(minc):
   t=src[idx];idx+=inc
   if idx>=size:idx-=size
   a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
 return bytes(o)
def verify(s:bytes)->bool:
 return len(s)==RAW and s[:12]==SYNC and s[15]==1 and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and s[0x814:0x81c]==bytes(8) and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88)
def rebuild(raw:bytes,user:bytes)->bytes:
 b=bytearray(raw);b[USER_OFF:USER_OFF+USER]=user
 b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8)
 b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88)
 o=bytes(b)
 if not verify(o):raise ValueError('MODE1 EDC/ECC rebuild failed')
 return o
def extract(disc:Path,lba:int,size:int)->bytes:
 out=bytearray();rem=size
 with disc.open('rb') as f:
  while rem:
   f.seek(lba*RAW);s=f.read(RAW)
   if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'not MODE1/2352 LBA {lba}')
   n=min(USER,rem);out+=s[USER_OFF:USER_OFF+n];rem-=n;lba+=1
 return bytes(out)
def diffs(a:Path,b:Path)->set[int]:
 out=set();i=0
 with a.open('rb') as x,b.open('rb') as y:
  while True:
   p=x.read(RAW);q=y.read(RAW)
   if not p and not q:break
   if len(p)!=len(q):raise ValueError('disc size mismatch')
   if p!=q:out.add(i)
   i+=1
 return out

def recover(root:Path,assets:list[dict],outdir:Path)->dict:
 outdir.mkdir(parents=True,exist_ok=True);need={Path(x['iso_path']).name:x for x in assets};hits={}
 def accept(name:str,data:bytes,src:str):
  if name not in need or name in hits:return
  x=need[name]
  if len(data)==x['size'] and shab(data)==x['replacement_sha256']:
   (outdir/name).write_bytes(data);hits[name]=src
 for p in root.rglob('*'):
  if not p.is_file():continue
  if p.name in need:
   try:accept(p.name,p.read_bytes(),str(p))
   except OSError:pass
  elif p.suffix.lower()=='.bin' and p.stat().st_size==DISC_SIZE:
   try:
    if shaf(p)==R37_SHA:
     for x in assets:accept(Path(x['iso_path']).name,extract(p,x['lba'],x['size']),f'R37_BIN:{p}')
   except (OSError,ValueError):pass
  elif p.suffix.lower()=='.zip':
   try:
    if shaf(p)!=R37_ZIP_SHA:continue
    with zipfile.ZipFile(p) as z:
     for zi in z.infolist():
      n=Path(zi.filename).name
      if n in need:accept(n,z.read(zi),f'R37_ZIP:{p}!{zi.filename}')
     bins=[zi for zi in z.infolist() if zi.file_size==DISC_SIZE]
     if len(hits)<len(need) and bins:
      with tempfile.TemporaryDirectory() as td:
       for zi in bins:
        q=Path(td)/'disc.bin'
        with z.open(zi) as src,q.open('wb') as dst:shutil.copyfileobj(src,dst,8*1024*1024)
        if shaf(q)==R37_SHA:
         for x in assets:accept(Path(x['iso_path']).name,extract(q,x['lba'],x['size']),f'R37_ZIP_BIN:{p}!{zi.filename}')
   except (OSError,zipfile.BadZipFile,ValueError):pass
 return hits

def main()->int:
 ap=argparse.ArgumentParser(description='Batch266 exact UI6 recovery + promotion onto exact Batch247')
 ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--search-root',type=Path,required=True)
 ap.add_argument('--manifest',type=Path,default=Path('manifests/CD1_BATCH266_UI6_R37_LINEAGE.json'))
 ap.add_argument('--candidate-dir',type=Path,default=Path('BATCH266_UI6_CANDIDATES'))
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B266_C2FIX_STATIC58_UI6_KO.bin'))
 ap.add_argument('--result',type=Path,default=Path('BATCH266_RESULT.json'))
 a=ap.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8'));xs=m['replacement_files']
 if m.get('format')!='ST2-CD1-BATCH266-UI6-R37-LINEAGE-v1' or len(xs)!=6:raise SystemExit('manifest/cardinality mismatch')
 if shaf(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine SHA mismatch')
 if shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA mismatch')
 for x in xs:
  if shab(extract(a.pristine,x['lba'],x['size']))!=x['source_sha256']:raise SystemExit(f"pristine source SHA failed: {x['iso_path']}")
 hits=recover(a.search_root,xs,a.candidate_dir)
 missing=[]
 for x in xs:
  n=Path(x['iso_path']).name;p=a.candidate_dir/n
  if not p.is_file() or p.stat().st_size!=x['size'] or shaf(p)!=x['replacement_sha256']:missing.append(n)
 if missing:
  a.result.write_text(json.dumps({'batch':266,'status':'BLOCKED_UI6_EXACT_PAYLOADS_MISSING','recovered':len(xs)-len(missing),'missing':missing,'hits':hits,'game_bytes_changed':0},ensure_ascii=False,indent=2),encoding='utf-8')
  print(f'BLOCKED: recovered {len(xs)-len(missing)}/6; missing {missing}');return 2
 shutil.copyfile(a.parent,a.output);changed=set();expected=[];per={}
 try:
  with a.parent.open('rb') as par,a.output.open('r+b') as dst:
   for x in xs:
    n=Path(x['iso_path']).name;c=(a.candidate_dir/n).read_bytes();rem=x['size'];pos=0;lba=x['lba'];cnt=0
    while rem:
     par.seek(lba*RAW);base=par.read(RAW)
     if len(base)!=RAW or not verify(base):raise ValueError(f'parent sector invalid LBA {lba}')
     take=min(USER,rem);u=bytearray(base[USER_OFF:USER_OFF+USER]);u[:take]=c[pos:pos+take];out=base
     if bytes(u)!=base[USER_OFF:USER_OFF+USER]:
      out=rebuild(base,bytes(u));dst.seek(lba*RAW);dst.write(out);changed.add(lba);cnt+=1
     expected.append({'asset':n,'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base})
     rem-=take;pos+=take;lba+=1
    per[n]={'changed_sectors':cnt,'replacement_sha256':x['replacement_sha256'],'recovered_from':hits.get(n,'preexisting-candidate-dir')}
  actual=diffs(a.parent,a.output)
  if actual!=changed:raise ValueError('changed-sector accounting mismatch')
  with a.output.open('rb') as f:
   for lba in changed:
    f.seek(lba*RAW)
    if not verify(f.read(RAW)):raise ValueError(f'EDC/ECC failure LBA {lba}')
  for x in xs:
   if shab(extract(a.output,x['lba'],x['size']))!=x['replacement_sha256']:raise ValueError(f"whole-asset re-extraction mismatch: {x['iso_path']}")
  result={'batch':266,'status':'PASS_B247_STATIC58_PLUS_UI6_EXECUTABLE_CANDIDATE','parent_sha256':PARENT_SHA,'ui_assets':6,'output_sha256':shaf(a.output),'changed_sectors':len(changed),'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'6/6 PASS','expected_write_records':len(expected),'guessed_payload_bytes':False,'per_asset':per,'expected_write':expected}
  a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ('expected_write','per_asset')},ensure_ascii=False,indent=2));return 0
 except Exception:
  a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
