#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

RAW=2352
USER_OFF=16
USER=2048
DISC_SIZE=659_293_824
DISC_SHA='e335f7e821821191bc7ecf6776b489949dac4dfe0e1ccdea6f7df8217053c6d8'
COMMON_SHA='5e89dd92af693ba37e20ab9516d6aca668c8c2a8fd6b480af54ff3b88067efa3'
ASSETS={
 'SYS06':(206791,80458),'SYS28':(207651,80458),'SYS30':(207732,80458),'SYS32':(207813,80458),
 'SYS35':(207935,80458),'SYS38':(208057,80458),'SYS39':(208097,80458),'SYS40':(208137,80458),
 'SYS41':(208177,80458),'SYS42':(208217,80458),'SYS43':(208257,80458),'SYS44':(208297,80458),
 'SYS48':(208460,80458),'SYS50':(208541,80458),
}

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def extract(p:Path,lba:int,size:int)->bytes:
 out=bytearray(); rem=size
 with p.open('rb') as f:
  while rem:
   f.seek(lba*RAW); sec=f.read(RAW)
   if len(sec)!=RAW: raise ValueError(f'short raw sector at LBA {lba}')
   n=min(USER,rem); out+=sec[USER_OFF:USER_OFF+n]; rem-=n; lba+=1
 return bytes(out)

def main()->int:
 ap=argparse.ArgumentParser(); ap.add_argument('candidate',type=Path); ap.add_argument('--json',type=Path); a=ap.parse_args()
 if a.candidate.stat().st_size!=DISC_SIZE: raise SystemExit(f'FAIL_SIZE {a.candidate.stat().st_size} != {DISC_SIZE}')
 whole=sha(a.candidate.read_bytes())
 if whole!=DISC_SHA: raise SystemExit(f'FAIL_DISC_SHA {whole}')
 checks={n:sha(extract(a.candidate,*g)) for n,g in ASSETS.items()}
 bad={n:h for n,h in checks.items() if h!=COMMON_SHA}
 if bad: raise SystemExit('FAIL_REEXTRACTION '+json.dumps(bad,sort_keys=True))
 result={'status':'PASS','candidate_size':DISC_SIZE,'candidate_sha256':whole,'common14':'14/14 PASS','assets':checks,'estimated_bytes':0}
 if a.json:a.json.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps(result,indent=2,sort_keys=True)); return 0
if __name__=='__main__':raise SystemExit(main())
