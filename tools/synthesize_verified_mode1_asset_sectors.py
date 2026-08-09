#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, hashlib, json, struct
from pathlib import Path
from typing import Any

RAW=2352; USER_OFF=16; USER=2048
SYNC=b'\x00'+b'\xff'*10+b'\x00'
EDC_LUT=[0]*256; ECC_F=[0]*256; ECC_B=[0]*256
for i in range(256):
    edc=i
    for _ in range(8): edc=(edc>>1) ^ (0xD8018001 if edc&1 else 0)
    EDC_LUT[i]=edc & 0xffffffff
    j=i<<1
    if j&0x100: j ^= 0x11d
    ECC_F[i]=j; ECC_B[i^j]=i

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def fsha(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
    return h.hexdigest()
def edc_compute(src:bytes, edc:int=0)->int:
    for v in src: edc=(edc>>8)^EDC_LUT[(edc^v)&0xff]
    return edc & 0xffffffff
def ecc_compute(src:bytes,major_count:int,minor_count:int,major_mult:int,minor_inc:int)->bytes:
    size=major_count*minor_count; out=bytearray(major_count*2)
    for major in range(major_count):
        idx=(major>>1)*major_mult+(major&1); a=b=0
        for _ in range(minor_count):
            t=src[idx]; idx+=minor_inc
            if idx>=size:idx-=size
            a^=t; b^=t; a=ECC_F[a]
        a=ECC_B[ECC_F[a]^b]; out[major]=a; out[major+major_count]=a^b
    return bytes(out)
def rebuild_mode1(sec:bytearray)->None:
    if len(sec)!=RAW or sec[15]!=1:raise ValueError('MODE1/2352 required')
    struct.pack_into('<I',sec,2064,edc_compute(sec[:2064])); sec[2068:2076]=b'\0'*8
    work=bytearray(sec); sec[2076:2248]=ecc_compute(work[12:2076],86,24,2,86)
    work=bytearray(sec); sec[2248:2352]=ecc_compute(work[12:2248],52,43,86,88)
def verify_mode1(sec:bytes)->bool:
    t=bytearray(sec); rebuild_mode1(t); return bytes(t)==sec
def bcd(v:int)->int:
    if not 0<=v<=99: raise ValueError(v)
    return ((v//10)<<4)|(v%10)
def raw_header(lba:int)->bytes:
    frames=lba+150; m=frames//(75*60); s=(frames//75)%60; f=frames%75
    return SYNC+bytes((bcd(m),bcd(s),bcd(f),1))
def synth_full(lba:int,user:bytes)->bytes:
    if len(user)!=USER:raise ValueError('full user sector required')
    sec=bytearray(RAW); sec[:16]=raw_header(lba); sec[16:2064]=user; rebuild_mode1(sec); return bytes(sec)
def load_assignments(path:Path)->dict[str,Any]:
    tree=ast.parse(path.read_text(encoding='utf-8'),filename=str(path)); out={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            n=node.targets[0].id
            if n in {'SECTORS','ASSETS','SOURCE_SHA','SOURCE_SIZE','OUTPUT_SHA'}:
                try: out[n]=ast.literal_eval(node.value)
                except Exception: pass
    if 'SECTORS' not in out or 'ASSETS' not in out:raise SystemExit('historical script missing literal SECTORS/ASSETS')
    return out

def main()->int:
    ap=argparse.ArgumentParser(description='Synthesize exact MODE1/2352 sector payloads from a whole candidate asset and verify them against historical patched-sector SHA-256. Never promotes partial/mismatching recovery.')
    ap.add_argument('--historical-apply',type=Path,required=True)
    ap.add_argument('--asset',required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--original-bin',type=Path,help='Required only if a changed sector is the asset partial final sector.')
    ap.add_argument('--output-dir',type=Path,default=Path('RECOVERED_PATCH_SECTORS'))
    ap.add_argument('--result',type=Path,default=Path('ASSET_SECTOR_RECOVERY_RESULT.json'))
    ap.add_argument('--diagnostic-on-candidate-sha-mismatch',action='store_true')
    args=ap.parse_args()
    d=load_assignments(args.historical_apply); assets=d['ASSETS']; sectors=d['SECTORS']
    if args.asset not in assets:raise SystemExit(f'asset not in historical ASSETS: {args.asset}')
    spec=assets[args.asset]; data=args.candidate.read_bytes(); cand_sha=sha(data)
    candidate_ok=len(data)==int(spec['size']) and cand_sha==spec['sha256']
    if not candidate_ok and not args.diagnostic_on_candidate_sha_mismatch:
        raise SystemExit(f'candidate whole SHA/size mismatch: got {len(data)} {cand_sha}; expected {spec["size"]} {spec["sha256"]}')
    owned=sorted((int(k),v) for k,v in sectors.items() if v.get('asset')==args.asset)
    rows=[]; good_payloads=[]; lba0=int(spec['lba']); size=int(spec['size'])
    orig=None
    if args.original_bin:
        if 'SOURCE_SIZE' in d and args.original_bin.stat().st_size!=int(d['SOURCE_SIZE']):raise SystemExit('original BIN size mismatch')
        if 'SOURCE_SHA' in d and fsha(args.original_bin)!=d['SOURCE_SHA']:raise SystemExit('original BIN SHA mismatch')
        orig=args.original_bin.open('rb')
    try:
        for lba,ss in owned:
            rel=lba-lba0; off=rel*USER; remaining=max(0,size-off); take=min(USER,remaining)
            if take<=0: raise SystemExit(f'historical sector outside asset: {lba}')
            if take==USER:
                raw=synth_full(lba,data[off:off+USER]); basis='candidate-full-user-sector'
            else:
                if orig is None:
                    rows.append({'lba':lba,'relative':rel,'status':'BLOCKED_PARTIAL_REQUIRES_ORIGINAL_BIN','take':take,'expected_patched_sha256':ss['patched_sha256']}); continue
                orig.seek(lba*RAW); rawb=bytearray(orig.read(RAW))
                if len(rawb)!=RAW or sha(bytes(rawb))!=ss['original_sha256']:raise SystemExit(f'Expected Write original sector mismatch LBA {lba}')
                rawb[USER_OFF:USER_OFF+take]=data[off:off+take]; rebuild_mode1(rawb); raw=bytes(rawb); basis='original-sector-template+candidate-partial-user'
            actual=sha(raw); ok=actual==ss['patched_sha256'] and verify_mode1(raw)
            rows.append({'lba':lba,'relative':rel,'take':take,'basis':basis,'actual_patched_sha256':actual,'expected_patched_sha256':ss['patched_sha256'],'mode1_edc_ecc':verify_mode1(raw),'match':ok})
            if ok:good_payloads.append((lba,raw,ss))
    finally:
        if orig:orig.close()
    exact=sum(1 for r in rows if r.get('match') is True); blocked=sum(1 for r in rows if str(r.get('status','')).startswith('BLOCKED'))
    all_sectors_ok=exact==len(owned) and blocked==0
    promotion_allowed=bool(candidate_ok and all_sectors_ok)
    written=[]
    if promotion_allowed:
        args.output_dir.mkdir(parents=True,exist_ok=True)
        for lba,raw,ss in good_payloads:
            p=args.output_dir/f'PATCHED_SECTOR_LBA{lba}.bin'; p.write_bytes(raw); written.append(str(p))
        manifest={'format':'ST2-EXACT-ASSET-RAW-SECTOR-RECOVERY-v1','asset':args.asset,'candidate_sha256':cand_sha,'historical_apply':args.historical_apply.name,'sector_count':len(owned),'expected_write_source_disc_sha256':d.get('SOURCE_SHA'),'sectors':[{'lba':lba,'original_sha256':ss['original_sha256'],'patched_sha256':ss['patched_sha256'],'file':f'PATCHED_SECTOR_LBA{lba}.bin'} for lba,_,ss in good_payloads]}
        (args.output_dir/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    result={'format':'ST2-EXACT-ASSET-RAW-SECTOR-RECOVERY-RESULT-v1','asset':args.asset,'candidate':str(args.candidate),'candidate_size':len(data),'candidate_sha256':cand_sha,'expected_candidate_size':size,'expected_candidate_sha256':spec['sha256'],'candidate_whole_sha_pass':candidate_ok,'historical_changed_sectors':len(owned),'sector_sha_pass':exact,'sector_blocked':blocked,'all_sector_sha_pass':all_sectors_ok,'promotion_allowed':promotion_allowed,'guessed_bytes':False,'rows':rows,'written_sector_payloads':written}
    args.result.parent.mkdir(parents=True,exist_ok=True); args.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'rows','written_sector_payloads'}},ensure_ascii=False,indent=2))
    return 0 if promotion_allowed else 2
if __name__=='__main__':raise SystemExit(main())
