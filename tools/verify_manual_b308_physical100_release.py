#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

RAW=2352
DISC_SIZE=659_293_824
PRISTINE_SHA="d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA="b3cc46918e3e3d5d7a1910776a079d3683d8b3a9961b3443dc0571cb99189e5f"
RESULT_SHA="1607f75d5b556338c38dfc08f1ba69ceae7b6afad3fdd8f876e9cbd0fa77eed6"
CERT_SHA="b673dd97381ab7a75616716854a276806b5c3b6702683cc9671e5b89a81c2184"
EW_SHA="5560411c5859f0b6454ed42493c733c3ad2f3fadfab33d323de25f029985b972"
EW_ROWS=66561
EW_CHANGED=51437
FULL_CHANGED=90128
SUCCESS="PASS_B308_MANUAL_PHYSICAL100_RELEASE_VERIFIED"

SYNC=bytes([0]+[0xFF]*10+[0])
def _edc_lut():
    out=[]
    for i in range(256):
        v=i
        for _ in range(8): v=(v>>1)^(0xD8018001 if v&1 else 0)
        out.append(v&0xffffffff)
    return out

def _ecc_luts():
    f,b=[0]*256,[0]*256
    for i in range(256):
        j=(i<<1)^(0x11D if i&0x80 else 0); f[i]=j&0xff; b[i^f[i]]=i
    return f,b
EDC_LUT=_edc_lut(); ECC_F,ECC_B=_ecc_luts()
def edc(data):
    v=0
    for x in data: v=(v>>8)^EDC_LUT[(v^x)&0xff]
    return v&0xffffffff
def ecc(src,major_count,minor_count,major_mult,minor_inc):
    size=major_count*minor_count; d=bytearray(major_count*2)
    for major in range(major_count):
        idx=(major>>1)*major_mult+(major&1); a=b=0
        for _ in range(minor_count):
            t=src[idx]; idx+=minor_inc
            if idx>=size: idx-=size
            a^=t; b^=t; a=ECC_F[a]
        a=ECC_B[ECC_F[a]^b]; d[major]=a; d[major+major_count]=a^b
    return bytes(d)
def mode1_valid(s):
    return (len(s)==RAW and s[:12]==SYNC and s[15]==1 and
            int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810]) and
            s[0x814:0x81c]==bytes(8) and
            s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86) and
            s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(8*1024*1024),b''): h.update(c)
    return h.hexdigest()
def die(s): raise SystemExit('FAIL '+s)
def require(v,msg):
    if not v: die(msg)

def main():
    ap=argparse.ArgumentParser(description='Verify the byte-exact B308 223/223 physical/static CD1 candidate and its frozen evidence.')
    ap.add_argument('--pristine-bin',type=Path,required=True)
    ap.add_argument('--candidate-bin',type=Path,required=True)
    ap.add_argument('--result-json',type=Path,required=True)
    ap.add_argument('--full223-cert',type=Path,required=True)
    ap.add_argument('--expected-write',type=Path,required=True)
    ap.add_argument('--deep-edc-ecc',action='store_true',help='recompute MODE1 EDC/ECC for every raw sector that differs from pristine')
    a=ap.parse_args()
    for p in [a.pristine_bin,a.candidate_bin,a.result_json,a.full223_cert,a.expected_write]: require(p.is_file(),f'missing {p}')
    require(a.pristine_bin.stat().st_size==DISC_SIZE,'pristine size')
    require(a.candidate_bin.stat().st_size==DISC_SIZE,'candidate size')
    require(sha(a.pristine_bin)==PRISTINE_SHA,'pristine SHA-256')
    require(sha(a.candidate_bin)==CANDIDATE_SHA,'candidate SHA-256')
    require(sha(a.result_json)==RESULT_SHA,'B308_RESULT evidence SHA-256')
    require(sha(a.full223_cert)==CERT_SHA,'B308_FULL223_CERT evidence SHA-256')
    require(sha(a.expected_write)==EW_SHA,'B308_EXPECTED_WRITE evidence SHA-256')

    r=json.loads(a.result_json.read_text(encoding='utf-8'))
    c=json.loads(a.full223_cert.read_text(encoding='utf-8'))
    ew=json.loads(a.expected_write.read_text(encoding='utf-8'))
    require(r.get('status')=='PASS_B308_REAL_PHYSICAL_STATIC_100_PERCENT_223_OF_223','result status')
    require(r.get('output_sha256')==CANDIDATE_SHA,'result/output binding')
    require(r.get('total_physical_static_assets_accounted')==223,'result 223 accounting')
    require(r.get('physical_static_coverage_percent')==100.0,'result coverage')
    require(r.get('cumulative_changed_sectors')==FULL_CHANGED,'result changed-sector count')
    require(r.get('guessed_payload_bytes')==0,'result guessed bytes')
    require(c.get('status')=='PASS_B308_FINAL_223_OF_223_WHOLE_ASSET_AND_ALL_CHANGED_SECTOR_GATE','full cert status')
    require(c.get('disc_sha256')==CANDIDATE_SHA,'full cert/disc binding')
    require(c.get('whole_asset_reextraction')=='223/223 PASS','223/223 re-extraction')
    require(c.get('changed_sector_count')==FULL_CHANGED,'cert changed-sector count')
    require(c.get('changed_sector_edc_ecc')=='90128/90128 PASS','cert EDC/ECC gate')
    require(c.get('group_accounting')=={'battle_static':58,'story':141,'movie':24},'group accounting')
    require(c.get('guessed_payload_bytes')==0,'cert guessed bytes')
    require(isinstance(ew,list) and len(ew)==EW_ROWS,'Expected Write row count')
    changed_rows=sum(bool(x.get('changed')) for x in ew)
    require(changed_rows==EW_CHANGED,'Expected Write changed row count')

    # Independent B308 delta Expected-Write replay: every footprint row must match the final raw sector SHA.
    seen=set()
    with a.candidate_bin.open('rb') as f:
        for row in ew:
            lba=row.get('lba'); require(isinstance(lba,int) and 0<=lba<DISC_SIZE//RAW,'Expected Write LBA')
            key=(row.get('asset'),lba); require(key not in seen,'duplicate Expected Write asset/LBA'); seen.add(key)
            f.seek(lba*RAW); sec=f.read(RAW)
            require(hashlib.sha256(sec).hexdigest()==row.get('output_sector_sha256'),f'Expected Write output SHA LBA {lba}')
            if row.get('changed'): require(mode1_valid(sec),f'B308 delta EDC/ECC LBA {lba}')

    # Independent exact raw-sector accounting from pristine to B308.
    diff=[]
    with a.pristine_bin.open('rb') as fp, a.candidate_bin.open('rb') as fc:
        for lba in range(DISC_SIZE//RAW):
            sp=fp.read(RAW); sc=fc.read(RAW)
            if sp!=sc:
                diff.append(lba)
                if a.deep_edc_ecc: require(mode1_valid(sc),f'full changed-sector EDC/ECC LBA {lba}')
    require(len(diff)==FULL_CHANGED,f'full raw-sector accounting {len(diff)} != {FULL_CHANGED}')
    print(SUCCESS)
    print('candidate_sha256='+CANDIDATE_SHA)
    print('physical_static_assets=223/223')
    print('whole_asset_reextraction=223/223 PASS')
    print(f'changed_sector_accounting={len(diff)}/{FULL_CHANGED} PASS')
    print('b308_delta_expected_write=66561/66561 PASS')
    print('b308_delta_changed_sector_edc_ecc=51437/51437 PASS')
    print('full_changed_sector_edc_ecc=' + ('90128/90128 RECOMPUTED PASS' if a.deep_edc_ecc else '90128/90128 FROZEN_CERT_TRUST_CHAIN_PASS'))
    print('hardware_validation=PENDING')
if __name__=='__main__': main()
