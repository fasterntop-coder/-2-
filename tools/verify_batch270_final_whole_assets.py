#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

RAW=2352
USER_OFF=16
USER=2048
PARENT_SHA='d37c3da740a2cbee168513fd2a6a1b5c7b6d8a2d9486dd6ce270544e50eb529a'
B269_STATUS='PASS_B247_STATIC58_PLUS_DEDUP_MASS137_EVENT34_EXECUTABLE_CANDIDATE'
SUCCESS='PASS_BATCH270_FINAL_UNION_WHOLE_ASSET_REEXTRACTION'


def sha_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()


def load_json(p:Path)->dict:
    return json.loads(p.read_text(encoding='utf-8'))


def normalize_asset(x:dict)->dict:
    need=('iso_path','lba','size','replacement_sha256')
    miss=[k for k in need if k not in x]
    if miss: raise SystemExit(f'manifest asset missing {miss}: {x}')
    return {
        'iso_path':str(x['iso_path']),
        'lba':int(x['lba']),
        'size':int(x['size']),
        'source_sha256':x.get('source_sha256'),
        'replacement_sha256':str(x['replacement_sha256']).lower(),
    }


def collect_manifest(path:Path, seen:set[Path]|None=None)->list[dict]:
    seen=set() if seen is None else seen
    path=path.resolve()
    if path in seen: return []
    seen.add(path)
    m=load_json(path)
    direct=m.get('replacement_files') or []
    out=[normalize_asset(x) for x in direct if x.get('replacement_sha256')]
    for c in m.get('components') or []:
        src=c.get('source') or c.get('manifest') or c.get('asset_manifest')
        if src:
            q=(Path.cwd()/src).resolve() if not Path(src).is_absolute() else Path(src).resolve()
            if q.exists(): out.extend(collect_manifest(q,seen))
    return out


def canonicalize(groups:list[tuple[str,list[dict]]])->dict[str,dict]:
    out={}
    origins={}
    for label,xs in groups:
        for x in xs:
            k=x['iso_path']
            sig=(x['lba'],x['size'],x['replacement_sha256'])
            if k in out:
                old=(out[k]['lba'],out[k]['size'],out[k]['replacement_sha256'])
                if old!=sig:
                    raise SystemExit(f'conflicting duplicate asset {k}: {old} != {sig}; sources={origins[k]} + {label}')
                origins[k].append(label)
            else:
                out[k]=x; origins[k]=[label]
    for k,v in out.items(): v['origins']=origins[k]
    return out


def extract_raw_iso_asset(f, lba:int, size:int)->bytes:
    remain=size; cur=lba; out=bytearray()
    while remain:
        f.seek(cur*RAW)
        sec=f.read(RAW)
        if len(sec)!=RAW: raise SystemExit(f'cannot read raw sector LBA {cur}')
        if sec[15] != 1: raise SystemExit(f'non-MODE1 sector at LBA {cur}')
        take=min(remain,USER)
        out += sec[USER_OFF:USER_OFF+take]
        remain-=take;cur+=1
    return bytes(out)


def require_pass(v,name):
    if 'PASS' not in str(v): raise SystemExit(f'{name} failed: {v!r}')


def main()->int:
    ap=argparse.ArgumentParser(description='Batch270: re-extract every exact promoted asset from the final Batch269 raw Disc1 candidate and verify SHA-256')
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--batch269-result',type=Path,required=True)
    ap.add_argument('--story109',type=Path,default=Path('manifests/CD1_BATCH253_STORY109_PROMOTION.json'))
    ap.add_argument('--story14',type=Path,default=Path('manifests/CD1_BATCH262_STORY14_CUMULATIVE.json'))
    ap.add_argument('--ui6',type=Path,default=Path('manifests/CD1_BATCH266_UI6_R37_LINEAGE.json'))
    ap.add_argument('--event34',type=Path,default=Path('manifests/CD1_BATCH244_EVENT34_PROMOTION.json'))
    ap.add_argument('--video10-sealed',type=Path,required=True,help='sealed Video10 manifest produced after exact package/payload recovery')
    ap.add_argument('--result',type=Path,default=Path('BATCH270_RESULT.json'))
    a=ap.parse_args()

    r=load_json(a.batch269_result)
    if r.get('status')!=B269_STATUS: raise SystemExit('Batch269 status gate failed')
    if r.get('parent_sha256')!=PARENT_SHA: raise SystemExit('Batch269 parent SHA gate failed')
    require_pass(r.get('expected_write'),'Batch269 Expected Write')
    require_pass(r.get('changed_sector_edc_ecc'),'Batch269 EDC/ECC')
    require_pass(r.get('changed_sector_accounting'),'Batch269 changed-sector accounting')
    actual_candidate_sha=sha_file(a.candidate)
    if actual_candidate_sha!=r.get('output_sha256'): raise SystemExit('Batch269 final candidate SHA mismatch')

    groups=[]
    for label,p in [('Story109',a.story109),('Story14',a.story14),('UI6',a.ui6),('Event34',a.event34),('Video10',a.video10_sealed)]:
        if not p.exists(): raise SystemExit(f'missing required exact manifest: {p}')
        xs=collect_manifest(p)
        if not xs: raise SystemExit(f'no exact replacement assets resolved from {label}: {p}')
        groups.append((label,xs))
    assets=canonicalize(groups)

    bad=[]; checked=[]
    with a.candidate.open('rb') as f:
        for path,x in sorted(assets.items()):
            payload=extract_raw_iso_asset(f,x['lba'],x['size'])
            got=sha_bytes(payload)
            ok=(got==x['replacement_sha256'])
            checked.append({'iso_path':path,'lba':x['lba'],'size':x['size'],'expected_sha256':x['replacement_sha256'],'actual_sha256':got,'status':'PASS' if ok else 'FAIL','origins':x['origins']})
            if not ok: bad.append(path)
    if bad: raise SystemExit(f'whole-asset SHA failures ({len(bad)}): {bad[:12]}')

    result={
        'batch':270,
        'status':SUCCESS,
        'input_batch':269,
        'parent_batch':247,
        'parent_sha256':PARENT_SHA,
        'final_candidate_sha256':actual_candidate_sha,
        'unique_exact_assets_reextracted':len(assets),
        'whole_asset_reextraction':f'{len(assets)}/{len(assets)} PASS',
        'deduplication':'PASS_BY_ISO_PATH_AND_IDENTICAL_LBA_SIZE_REPLACEMENT_SHA256',
        'batch269_expected_write':'PASS',
        'batch269_changed_sector_edc_ecc':'PASS',
        'batch269_changed_sector_accounting':'PASS',
        'guessed_payload_bytes':False,
        'assets':checked,
    }
    a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='assets'},ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
