#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil
from pathlib import Path

RAW=2352
SYNC=bytes([0]+[0xFF]*10+[0])
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
B267_STATUS='PASS_B247_STATIC58_PLUS_137_ASSET_CUMULATIVE_EXECUTABLE_CANDIDATE'
B248_STATUS='PASS_B247_PLUS_EVENT34_EXECUTABLE_CANDIDATE'


def shaf(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()


def _edc_lut():
    out=[]
    for i in range(256):
        v=i
        for _ in range(8): v=(v>>1)^(0xD8018001 if v&1 else 0)
        out.append(v&0xffffffff)
    return out
EDC=_edc_lut()

def edc(d:bytes)->int:
    v=0
    for x in d: v=(v>>8)^EDC[(v^x)&255]
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
            t=src[idx];idx=(idx+inc)%size;a^=t;b^=t;a=EF[a]
        a=EB[EF[a]^b];o[m]=a;o[m+maj]=a^b
    return bytes(o)

def verify_mode1(s:bytes)->bool:
    return (len(s)==RAW and s[:12]==SYNC and s[15]==1
        and int.from_bytes(s[0x810:0x814],'little')==edc(s[:0x810])
        and s[0x814:0x81c]==bytes(8)
        and s[0x81c:0x8c8]==ecc(s[0x0c:0x81c],86,24,2,86)
        and s[0x8c8:0x930]==ecc(s[0x0c:0x8c8],52,43,86,88))


def diffs(parent:Path,candidate:Path)->dict[int,bytes]:
    out={};i=0
    with parent.open('rb') as a,candidate.open('rb') as b:
        while True:
            x=a.read(RAW);y=b.read(RAW)
            if not x and not y: break
            if len(x)!=len(y): raise SystemExit('disc size mismatch')
            if x!=y: out[i]=y
            i+=1
    return out


def require_pass(v,name):
    if 'PASS' not in str(v): raise SystemExit(f'{name} failed: {v!r}')


def canonical_assets(m:dict)->dict[str,dict]:
    xs=m.get('replacement_files') or []
    out={}
    for x in xs:
        key=x['iso_path']
        y={k:x[k] for k in ('iso_path','lba','size','source_sha256','replacement_sha256')}
        if key in out and out[key]!=y: raise SystemExit(f'conflicting duplicate in manifest: {key}')
        out[key]=y
    return out


def main()->int:
    ap=argparse.ArgumentParser(description='Batch269: exact deduplicated union of Batch267 mass137 and Batch248 Event34 on Batch247')
    ap.add_argument('--parent',type=Path,required=True,help='exact Batch247 BIN')
    ap.add_argument('--mass137',type=Path,required=True,help='Batch267 candidate BIN')
    ap.add_argument('--mass137-result',type=Path,required=True)
    ap.add_argument('--event34',type=Path,required=True,help='Batch248 candidate BIN')
    ap.add_argument('--event34-result',type=Path,required=True)
    ap.add_argument('--story109-manifest',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
    ap.add_argument('--event34-manifest',type=Path,default=Path('manifests/CD1_BATCH244_EVENT34_PROMOTION.json'))
    ap.add_argument('--union-manifest',type=Path,default=Path('manifests/CD1_BATCH269_EVENT34_PLUS_137_UNION.json'))
    ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B269_Static58_Mass137_Event34_KO.bin'))
    ap.add_argument('--result',type=Path,default=Path('BATCH269_RESULT.json'))
    a=ap.parse_args()

    u=json.loads(a.union_manifest.read_text(encoding='utf-8'))
    if u.get('format')!='ST2-CD1-BATCH269-EVENT34-PLUS-137-UNION-v1': raise SystemExit('Batch269 manifest format mismatch')
    if shaf(a.parent)!=PARENT_SHA: raise SystemExit('Batch247 parent SHA mismatch')

    r267=json.loads(a.mass137_result.read_text(encoding='utf-8'))
    r248=json.loads(a.event34_result.read_text(encoding='utf-8'))
    if r267.get('status')!=B267_STATUS or r267.get('parent_sha256')!=PARENT_SHA: raise SystemExit('Batch267 lineage/status gate failed')
    if r248.get('status')!=B248_STATUS or r248.get('parent_sha256')!=PARENT_SHA: raise SystemExit('Batch248 lineage/status gate failed')
    if shaf(a.mass137)!=r267.get('output_sha256'): raise SystemExit('Batch267 output SHA mismatch')
    if shaf(a.event34)!=r248.get('output_sha256'): raise SystemExit('Batch248 output SHA mismatch')
    if r267.get('new_replacement_assets')!=137: raise SystemExit('Batch267 asset count mismatch')
    if r248.get('event_assets_promoted')!=34: raise SystemExit('Batch248 asset count mismatch')
    require_pass(r267.get('changed_sector_accounting'),'Batch267 changed-sector accounting')
    require_pass(r267.get('changed_sector_edc_ecc'),'Batch267 EDC/ECC')
    require_pass(r267.get('whole_asset_reextraction_preservation'),'Batch267 whole-asset gate')
    require_pass(r248.get('changed_sector_edc_ecc'),'Batch248 EDC/ECC')
    require_pass(r248.get('whole_asset_reextraction'),'Batch248 whole-asset gate')

    story=canonical_assets(json.loads(a.story109_manifest.read_text(encoding='utf-8')))
    event=canonical_assets(json.loads(a.event34_manifest.read_text(encoding='utf-8')))
    if len(story)!=107 or len(event)!=34: raise SystemExit('asset manifest cardinality mismatch')
    overlap=sorted(set(story)&set(event))
    conflicts=[p for p in overlap if story[p]['replacement_sha256']!=event[p]['replacement_sha256']]
    if conflicts: raise SystemExit(f'logical asset SHA conflicts: {conflicts[:8]}')
    unique_event=sorted(set(event)-set(story))
    unique_new_assets=137+len(unique_event)

    s267=diffs(a.parent,a.mass137);s248=diffs(a.parent,a.event34)
    overlap_lbas=sorted(set(s267)&set(s248))
    sector_conflicts=[lba for lba in overlap_lbas if s267[lba]!=s248[lba]]
    if sector_conflicts: raise SystemExit(f'changed-sector conflicts: {sector_conflicts[:8]}')
    union=dict(s267);union.update(s248)

    shutil.copyfile(a.parent,a.output)
    with a.output.open('r+b') as f:
        for lba,sector in sorted(union.items()):
            f.seek(lba*RAW);f.write(sector)
    bad=[];identity_bad=[]
    with a.output.open('rb') as f:
        for lba,sector in sorted(union.items()):
            f.seek(lba*RAW);got=f.read(RAW)
            if got!=sector: identity_bad.append(lba)
            if not verify_mode1(got): bad.append(lba)
    if identity_bad: raise SystemExit(f'Expected Write identity failures: {identity_bad[:8]}')
    if bad: raise SystemExit(f'MODE1 EDC/ECC failures: {bad[:8]}')
    outsha=shaf(a.output)
    result={
      'batch':269,
      'status':'PASS_B247_STATIC58_PLUS_DEDUP_MASS137_EVENT34_EXECUTABLE_CANDIDATE',
      'parent_batch':247,'parent_sha256':PARENT_SHA,
      'mass137_candidate_sha256':r267['output_sha256'],'event34_candidate_sha256':r248['output_sha256'],
      'declared_component_assets':171,
      'story109_event34_logical_overlap':len(overlap),
      'event34_assets_new_beyond_story109':len(unique_event),
      'unique_new_replacement_assets':unique_new_assets,
      'cumulative_parent_static_plus_unique_new_assets':58+unique_new_assets,
      'mass137_changed_sectors':len(s267),'event34_changed_sectors':len(s248),
      'identical_changed_sector_overlap':len(overlap_lbas),'conflicting_changed_sector_overlap':0,
      'union_changed_sectors':len(union),'expected_write_records':len(union),
      'expected_write':f'{len(union)}/{len(union)} PASS',
      'changed_sector_edc_ecc':f'{len(union)}/{len(union)} PASS',
      'changed_sector_accounting':'PASS','final_component_sector_identity':'PASS',
      'whole_asset_reextraction_preservation':'PASS_BY_COMPONENT_WHOLE_ASSET_GATES_PLUS_BYTE_IDENTICAL_OVERLAP',
      'output_sha256':outsha,'guessed_payload_bytes':False,
      'overlap_iso_paths':overlap,'unique_event34_iso_paths':unique_event
    }
    a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0

if __name__=='__main__': raise SystemExit(main())
