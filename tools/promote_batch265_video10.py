#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,math,shutil
from pathlib import Path
RAW=2352;USER_OFF=16;USER=2048;SYNC=bytes([0]+[255]*10+[0]);PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a';PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
def shab(b):return hashlib.sha256(b).hexdigest()
def shaf(p):
 h=hashlib.sha256();f=p.open('rb')
 while c:=f.read(8*1024*1024):h.update(c)
 f.close();return h.hexdigest()
def lut_edc():
 o=[]
 for i in range(256):
  v=i
  for _ in range(8):v=(v>>1)^(0xD8018001 if v&1 else 0)
  o.append(v&0xffffffff)
 return o
EDC=lut_edc()
def edc(d):
 v=0
 for x in d:v=(v>>8)^EDC[(v^x)&255]
 return v&0xffffffff
def luts():
 f=[0]*256;b=[0]*256
 for i in range(256):j=(i<<1)^(0x11D if i&0x80 else 0);f[i]=j&255;b[i^f[i]]=i
 return f,b
EF,EB=luts()
def ecc(src,maj,minc,mult,inc):
 size=maj*minc;o=bytearray(maj*2)
 for m in range(maj):
  idx=(m>>1)*mult+(m&1);a=b=0
  for _ in range(minc):t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
  a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
 return bytes(o)
def verify(s):return len(s)==RAW and s[:12]==SYNC and s[15]==1 and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and s[0x814:0x81c]==bytes(8) and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88)
def rebuild(raw,user):
 b=bytearray(raw);b[16:2064]=user;b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8);b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88);o=bytes(b)
 if not verify(o):raise ValueError('EDC/ECC rebuild failure')
 return o
def extract(disc,lba,size):
 o=bytearray();r=size
 with disc.open('rb') as f:
  while r:
   f.seek(lba*RAW);s=f.read(RAW)
   if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'bad MODE1 sector {lba}')
   n=min(USER,r);o+=s[16:16+n];r-=n;lba+=1
 return bytes(o)
def diffs(a,b):
 out=set();i=0
 with a.open('rb') as x,b.open('rb') as y:
  while True:
   p=x.read(RAW);q=y.read(RAW)
   if not p and not q:break
   if len(p)!=len(q):raise ValueError('disc size mismatch')
   if p!=q:out.add(i)
   i+=1
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--candidate-dir',type=Path,required=True);ap.add_argument('--sealed',type=Path,default=Path('manifests/CD1_BATCH264_VIDEO10_SEALED.json'));ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B265_C2FIX_STATIC58_VIDEO10_KO.bin'));ap.add_argument('--result',type=Path,default=Path('BATCH265_RESULT.json'));a=ap.parse_args()
 if shaf(a.pristine)!=PRISTINE_SHA or shaf(a.parent)!=PARENT_SHA:raise SystemExit('disc SHA gate failed')
 m=json.loads(a.sealed.read_text(encoding='utf-8'))
 if m.get('status')!='PASS_VIDEO10_10_OF_10_SEALED' or m.get('recovered_count')!=10:raise SystemExit('Video10 seal incomplete')
 assets=m['assets'];foot=set()
 for x in assets:
  n=Path(x['iso_path']).name;p=a.candidate_dir/n;h=x.get('sealed_replacement_sha256')
  if not p.is_file() or p.stat().st_size!=x['size'] or shaf(p)!=h:raise SystemExit(f'candidate gate failed {n}')
  if shab(extract(a.pristine,x['lba'],x['size']))!=x['source_sha256']:raise SystemExit(f'pristine source gate failed {n}')
  ls=set(range(x['lba'],x['lba']+math.ceil(x['size']/USER)))
  if foot&ls:raise SystemExit(f'Video10 footprint collision {n}')
  foot|=ls
 old=diffs(a.pristine,a.parent)
 if old&foot:raise SystemExit(f'parent overlap LBA {min(old&foot)}')
 shutil.copyfile(a.parent,a.output);changed=set();expected=[]
 try:
  with a.parent.open('rb') as par,a.output.open('r+b') as dst:
   for x in assets:
    n=Path(x['iso_path']).name;c=(a.candidate_dir/n).read_bytes();r=x['size'];pos=0;lba=x['lba']
    while r:
     par.seek(lba*RAW);base=par.read(RAW);take=min(USER,r);u=bytearray(base[16:2064]);u[:take]=c[pos:pos+take];out=base
     if bytes(u)!=base[16:2064]:out=rebuild(base,bytes(u));dst.seek(lba*RAW);dst.write(out);changed.add(lba)
     expected.append({'asset':n,'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base});r-=take;pos+=take;lba+=1
  actual=diffs(a.parent,a.output)
  if actual!=changed or not changed<=foot:raise ValueError('changed-sector accounting failed')
  with a.output.open('rb') as f:
   for lba in changed:f.seek(lba*RAW);s=f.read(RAW);assert verify(s),f'EDC/ECC failure {lba}'
  for x in assets:
   n=Path(x['iso_path']).name
   if shab(extract(a.output,x['lba'],x['size']))!=x['sealed_replacement_sha256']:raise ValueError(f're-extraction failure {n}')
  res={'batch':265,'status':'PASS_B247_STATIC58_PLUS_VIDEO10_EXECUTABLE_CANDIDATE','parent_sha256':PARENT_SHA,'video_assets_promoted':10,'output_sha256':shaf(a.output),'approved_footprint_sectors':len(foot),'changed_sectors':len(changed),'parent_overlap':0,'outside_footprint_changes':0,'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'10/10 PASS','expected_write_records':len(expected),'guessed_payload_bytes':False}
  a.result.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2));return 0
 except Exception:a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
