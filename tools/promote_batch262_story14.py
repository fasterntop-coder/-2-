#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, shutil
from pathlib import Path
RAW=2352; USER_OFF=16; USER=2048; SYNC=bytes([0]+[0xFF]*10+[0])
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
DYNAMIC={
 'SK0306.BIN':{'iso_path':'SAKURA1/SK0306.BIN','lba':45428,'size':50464,'source_sha256':'3bc3ef87fb0843a9bf2b71fa37ee168bdc1a84ed9ba9723eb52e6ca68e647455'},
 'SK0401.BIN':{'iso_path':'SAKURA1/SK0401.BIN','lba':45453,'size':104080,'source_sha256':'2f9a8d68405b330103dfe517fbcf8af6615cab2ddb2554d29d59fc155194b786'},
 'SK0402.BIN':{'iso_path':'SAKURA1/SK0402.BIN','lba':45504,'size':249824,'source_sha256':'99acc63f1224017588d9e91fd862b83683d45ea3a338fe711033dd94ed0c7852'}
}
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
 b=bytearray(raw);b[USER_OFF:USER_OFF+USER]=user;b[0x810:0x814]=edc(bytes(b[:0x810])).to_bytes(4,'little');b[0x814:0x81c]=bytes(8);b[0x81c:0x8c8]=ecc(bytes(b[0x0c:0x81c]),86,24,2,86);b[0x8c8:0x930]=ecc(bytes(b[0x0c:0x8c8]),52,43,86,88);o=bytes(b)
 if not verify(o):raise ValueError('EDC/ECC rebuild failed')
 return o
def extract(disc:Path,lba:int,size:int)->bytes:
 out=bytearray();r=size
 with disc.open('rb') as f:
  while r:
   f.seek(lba*RAW);s=f.read(RAW)
   if len(s)!=RAW or s[:12]!=SYNC or s[15]!=1:raise ValueError(f'not MODE1/2352 LBA {lba}')
   n=min(USER,r);out+=s[USER_OFF:USER_OFF+n];r-=n;lba+=1
 return bytes(out)
def load_dynamic(b260:Path,b261:Path)->dict[str,str]:
 a=json.loads(b260.read_text(encoding='utf-8'));b=json.loads(b261.read_text(encoding='utf-8'));out={}
 if a.get('asset')!='SK0401.BIN' or not a.get('replacement_sha256'):raise SystemExit('Batch260 result missing exact SK0401 SHA')
 out['SK0401.BIN']=a['replacement_sha256']
 rr=b.get('recovered_lineages',{})
 for tag,n in [('R40B','SK0306.BIN'),('R40D','SK0402.BIN')]:
  x=rr.get(tag,{})
  if x.get('asset')!=n or not x.get('sha256'):raise SystemExit(f'Batch261 result missing exact {n} SHA')
  out[n]=x['sha256']
 return out
def main()->int:
 ap=argparse.ArgumentParser(description='Batch262 exact fourteen-bank story promotion onto Batch247')
 ap.add_argument('--pristine',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--candidate-dir',type=Path,required=True)
 ap.add_argument('--story11-manifest',type=Path,default=Path('manifests/CD1_BATCH259_STORY11_MEGA_PROMOTION.json'))
 ap.add_argument('--batch260-result',type=Path,required=True);ap.add_argument('--batch261-result',type=Path,required=True)
 ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B262_B247_STORY14_KO.bin'));ap.add_argument('--result',type=Path,default=Path('BATCH262_RESULT.json'))
 a=ap.parse_args()
 if shaf(a.pristine)!=PRISTINE_SHA:raise SystemExit('pristine SHA mismatch')
 if shaf(a.parent)!=PARENT_SHA:raise SystemExit('Batch247 parent SHA mismatch')
 m=json.loads(a.story11_manifest.read_text(encoding='utf-8'));xs=[]
 if m.get('asset_count')!=11:raise SystemExit('Story11 manifest cardinality mismatch')
 for x in m['replacement_files']:xs.append(dict(x))
 dynsha=load_dynamic(a.batch260_result,a.batch261_result)
 for n,x in DYNAMIC.items():xs.append({**x,'replacement_sha256':dynsha[n]})
 if len(xs)!=14 or len({x['iso_path'] for x in xs})!=14:raise SystemExit('Story14 cardinality/duplicate mismatch')
 footprint=set();cands={}
 for x in xs:
  n=Path(x['iso_path']).name;p=a.candidate_dir/n
  if not p.is_file() or p.stat().st_size!=x['size'] or shaf(p)!=x['replacement_sha256']:raise SystemExit(f'exact candidate gate failed: {n}')
  if shab(extract(a.pristine,x['lba'],x['size']))!=x['source_sha256']:raise SystemExit(f'pristine source SHA failed: {n}')
  ls=set(range(x['lba'],x['lba']+math.ceil(x['size']/USER)))
  if footprint&ls:raise SystemExit(f'intra-story footprint collision: {n}')
  footprint|=ls;cands[n]=p
 shutil.copyfile(a.parent,a.output);changed=set();expected=[]
 try:
  with a.pristine.open('rb') as pri,a.parent.open('rb') as par,a.output.open('r+b') as dst:
   for x in sorted(xs,key=lambda z:z['lba']):
    n=Path(x['iso_path']).name;c=cands[n].read_bytes();r=x['size'];pos=0;lba=x['lba']
    while r:
     pri.seek(lba*RAW);src=pri.read(RAW);par.seek(lba*RAW);base=par.read(RAW)
     if src!=base:raise ValueError(f'Batch247 overlap/Expected Write mismatch LBA {lba}')
     take=min(USER,r);u=bytearray(base[USER_OFF:USER_OFF+USER]);u[:take]=c[pos:pos+take];out=base if bytes(u)==base[USER_OFF:USER_OFF+USER] else rebuild(base,bytes(u))
     if out!=base:dst.seek(lba*RAW);dst.write(out);changed.add(lba)
     expected.append({'asset':n,'lba':lba,'expected_parent_sha256':shab(base),'written_sha256':shab(out),'changed':out!=base})
     r-=take;pos+=take;lba+=1
  if not changed<=footprint:raise ValueError('change outside approved footprint')
  with a.output.open('rb') as f:
   for lba in changed:
    f.seek(lba*RAW)
    if not verify(f.read(RAW)):raise ValueError(f'EDC/ECC failure LBA {lba}')
  re={}
  for x in xs:
   n=Path(x['iso_path']).name;h=shab(extract(a.output,x['lba'],x['size']))
   if h!=x['replacement_sha256']:raise ValueError(f'whole-asset re-extraction mismatch: {n}')
   re[n]=h
  result={'batch':262,'status':'PASS_B247_PLUS_STORY14_EXECUTABLE_CANDIDATE','story_assets_promoted':14,'output_sha256':shaf(a.output),'approved_footprint_sectors':len(footprint),'changed_sectors':len(changed),'parent_overlap':0,'outside_footprint_changes':0,'changed_sector_edc_ecc':f'{len(changed)}/{len(changed)} PASS','whole_asset_reextraction':'14/14 PASS','expected_write_records':len(expected),'reextracted_sha256':re,'guessed_payload_bytes':False}
  a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except Exception:
  a.output.unlink(missing_ok=True);raise
if __name__=='__main__':raise SystemExit(main())
