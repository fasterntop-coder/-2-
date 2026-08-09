#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, io, json, math, shutil, tempfile, zipfile
from pathlib import Path

RAW=2352; USER_OFF=16; USER=2048; DISC_SIZE=659293824
SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
TARGETS={
 'R40B':{'disc_sha':'2db06a0695da7e14eefe448dbcc4d026857ce427669d2fc975fc93a4d742e119','name':'SK0306.BIN','lba':45428,'size':50464,'orig':'3bc3ef87fb0843a9bf2b71fa37ee168bdc1a84ed9ba9723eb52e6ca68e647455'},
 'R40D':{'disc_sha':'125bbc3f5c409fef24c1adc25b69f08a9062934b9ec2db97b3f44b7be7d74512','name':'SK0402.BIN','lba':45504,'size':249824,'orig':'99acc63f1224017588d9e91fd862b83683d45ea3a338fe711033dd94ed0c7852'}
}

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  while c:=f.read(8*1024*1024):h.update(c)
 return h.hexdigest()
def hash_stream(f)->str:
 h=hashlib.sha256()
 while c:=f.read(8*1024*1024):h.update(c)
 return h.hexdigest()
def extract(disc:Path,lba:int,size:int)->bytes:
 out=bytearray();remain=size
 with disc.open('rb') as f:
  while remain:
   f.seek(lba*RAW);s=f.read(RAW)
   if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'not MODE1/2352 LBA {lba}')
   n=min(USER,remain);out+=s[USER_OFF:USER_OFF+n];remain-=n;lba+=1
 return bytes(out)
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
 if not verify(o):raise ValueError('EDC/ECC rebuild failed')
 return o

def find_lineages(root:Path,tmp:Path)->dict[str,Path]:
 wanted={v['disc_sha']:k for k,v in TARGETS.items()};found={}
 for p in root.rglob('*'):
  if len(found)==len(TARGETS):break
  try:
   if p.is_file() and p.suffix.lower()=='.bin' and p.stat().st_size==DISC_SIZE:
    h=shaf(p)
    if h in wanted and wanted[h] not in found:found[wanted[h]]=p
   elif p.is_file() and p.suffix.lower()=='.zip':
    with zipfile.ZipFile(p) as z:
     for zi in z.infolist():
      if zi.file_size!=DISC_SIZE or not zi.filename.lower().endswith('.bin'):continue
      with z.open(zi) as f:h=hash_stream(f)
      if h not in wanted or wanted[h] in found:continue
      out=tmp/f'{wanted[h]}_disc.bin'
      with z.open(zi) as src,out.open('wb') as dst:shutil.copyfileobj(src,dst,8*1024*1024)
      if shaf(out)!=h:raise ValueError('ZIP materialization SHA mismatch')
      found[wanted[h]]=out
  except (OSError,zipfile.BadZipFile):continue
 return found

def main()->int:
 ap=argparse.ArgumentParser(description='Batch261 exact R40B/R40D story2 recovery and Batch247 promotion')
 ap.add_argument('--search-root',type=Path,required=True);ap.add_argument('--pristine',type=Path);ap.add_argument('--parent',type=Path)
 ap.add_argument('--recovered-dir',type=Path,default=Path('BATCH261_RECOVERED'))
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B261_B247_STORY2_KO.bin'))
 ap.add_argument('--result',type=Path,default=Path('BATCH261_RESULT.json'))
 a=ap.parse_args();a.recovered_dir.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='st2b261_') as td:
  found=find_lineages(a.search_root,Path(td));recovered={}
  for tag,t in TARGETS.items():
   if tag not in found:continue
   if shaf(found[tag])!=t['disc_sha']:raise SystemExit(f'{tag} full-disc SHA gate failed')
   payload=extract(found[tag],t['lba'],t['size']);ph=shab(payload)
   if ph==t['orig']:raise SystemExit(f'{tag} target asset remained pristine; refusing promotion')
   out=a.recovered_dir/t['name'];out.write_bytes(payload)
   recovered[tag]={'asset':t['name'],'sha256':ph,'size':len(payload),'source_disc_sha256':t['disc_sha']}
  result={'batch':261,'recovered_lineages':recovered,'recovered_assets':len(recovered),'required_assets':2,'guessed_bytes':False}
  if len(recovered)<2:
   result['status']='PARTIAL_EXACT_RECOVERY';a.result.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 2
  if not a.pristine or not a.parent:
   result['status']='PASS_EXACT_TWO_ASSET_RECOVERY_READY_FOR_PROMOTION';a.result.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0
  if shaf(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine disc SHA mismatch')
  if shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA mismatch')
  for t in TARGETS.values():
   if shab(extract(a.pristine,t['lba'],t['size']))!=t['orig']:raise SystemExit(f"pristine asset SHA mismatch: {t['name']}")
  shutil.copyfile(a.parent,a.output);changed=set();expected=[]
  with a.pristine.open('rb') as pri,a.parent.open('rb') as par,a.output.open('r+b') as dst:
   for tag,t in TARGETS.items():
    c=(a.recovered_dir/t['name']).read_bytes();remain=t['size'];pos=0;lba=t['lba']
    while remain:
     pri.seek(lba*RAW);src=pri.read(RAW);par.seek(lba*RAW);base=par.read(RAW)
     if src!=base:raise SystemExit(f'Batch247 overlap/Expected Write mismatch LBA {lba}')
     take=min(USER,remain);u=bytearray(base[USER_OFF:USER_OFF+USER]);u[:take]=c[pos:pos+take]
     out=base if bytes(u)==base[USER_OFF:USER_OFF+USER] else rebuild(base,bytes(u))
     if out!=base:dst.seek(lba*RAW);dst.write(out);changed.add(lba)
     expected.append({'asset':t['name'],'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base})
     remain-=take;pos+=take;lba+=1
  with a.output.open('rb') as f:
   for lba in changed:
    f.seek(lba*RAW)
    if not verify(f.read(RAW)):raise SystemExit(f'EDC/ECC failure LBA {lba}')
  reextract={}
  for tag,t in TARGETS.items():
   h=shab(extract(a.output,t['lba'],t['size']));want=recovered[tag]['sha256']
   if h!=want:raise SystemExit(f"whole-asset re-extraction mismatch: {t['name']}")
   reextract[t['name']]=h
  result.update({'status':'PASS_B247_PLUS_R40BD_STORY2_EXECUTABLE_CANDIDATE','output_sha256':shaf(a.output),'story_assets_promoted':2,'story_records_promoted':1742,'changed_sectors':len(changed),'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','expected_write_records':len(expected),'whole_asset_reextraction':'2/2 PASS','reextracted_sha256':reextract,'parent_overlap':0})
  a.result.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
