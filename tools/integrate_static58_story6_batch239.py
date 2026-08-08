#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

RAW=2352
USER_OFF=16
USER=2048
HERE=Path(__file__).resolve().parent
REPO=HERE.parent
DEFAULT_STORY=REPO/'manifests'/'CD1_STORY_EXACT_STRUCTURE_BATCH236.json'
DEFAULT_STATIC=REPO/'manifests'/'BATCH200_REAL_FULL58_RECOVERY.json'
EXPECTED_STATIC_DISC_SHA='75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20'
EXPECTED_FINAL_SHA='daa1052fabd4142feaf42f14bdb5deefdf486cea8f0db8c939fc18ce6f822a56'
EXPECTED_STATIC_CHANGED=1626
EXPECTED_STORY_CHANGED=275
EXPECTED_UNION_CHANGED=1901


def sha_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(8*1024*1024): h.update(chunk)
    return h.hexdigest()


def import_mode1():
    sys.path.insert(0,str(HERE))
    import mode1_2352 as m
    return m


def extract_asset(disc:Path,lba:int,size:int)->bytes:
    out=bytearray(); remain=size
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW+USER_OFF)
            take=min(USER,remain)
            b=f.read(take)
            if len(b)!=take: raise ValueError(f'short user data at LBA {lba}')
            out.extend(b); remain-=take; lba+=1
    return bytes(out)


def extent_lbas(lba:int,size:int)->set[int]:
    return set(range(lba,lba+math.ceil(size/USER)))


def patch_sector(mode1,raw:bytes,user:bytes)->bytes:
    if len(raw)!=RAW or len(user)!=USER: raise ValueError('sector geometry')
    b=bytearray(raw); b[USER_OFF:USER_OFF+USER]=user
    b[0x810:0x814]=mode1.edc(bytes(b[:0x810])).to_bytes(4,'little')
    b[0x814:0x81C]=bytes(8)
    b[0x81C:0x8C8]=mode1._ecc_compute(bytes(b[0x0C:0x81C]),86,24,2,86)
    b[0x8C8:0x930]=mode1._ecc_compute(bytes(b[0x0C:0x8C8]),52,43,86,88)
    mode1.assert_mode1_sector(bytes(b),'patched')
    return bytes(b)


def diff_lbas(left:Path,right:Path,mode1=None)->list[int]:
    out=[]
    with left.open('rb') as a,right.open('rb') as b:
        lba=0
        while True:
            x=a.read(RAW); y=b.read(RAW)
            if not x and not y: break
            if len(x)!=len(y): raise ValueError('disc size mismatch during diff')
            if x!=y:
                if mode1: mode1.assert_mode1_sector(y,f'changed output LBA {lba}')
                out.append(lba)
            lba+=1
    return out


def main()->int:
    ap=argparse.ArgumentParser(description='Batch239 exact union of verified static58 baseline and six exact story replacements')
    ap.add_argument('--pristine',type=Path,required=True)
    ap.add_argument('--static-baseline',type=Path,required=True)
    ap.add_argument('--candidate-dir',type=Path,required=True)
    ap.add_argument('--story-manifest',type=Path,default=DEFAULT_STORY)
    ap.add_argument('--static-manifest',type=Path,default=DEFAULT_STATIC)
    ap.add_argument('--output',type=Path,default=Path('Sakura_Taisen_2_Disc1_B239_Static58_Story6_KO.bin'))
    ap.add_argument('--result',type=Path,default=Path('BATCH239_RESULT.json'))
    args=ap.parse_args()
    story=json.loads(args.story_manifest.read_text(encoding='utf-8'))
    static=json.loads(args.static_manifest.read_text(encoding='utf-8'))
    mode1=import_mode1()

    if args.pristine.stat().st_size!=story['source_disc']['size'] or sha_file(args.pristine)!=story['source_disc']['sha256']:
        raise SystemExit('pristine Disc1 size/SHA mismatch')
    if args.static_baseline.stat().st_size!=args.pristine.stat().st_size or sha_file(args.static_baseline)!=EXPECTED_STATIC_DISC_SHA:
        raise SystemExit('static58 parent Disc SHA mismatch')
    if static['output_disc_sha256']!=EXPECTED_STATIC_DISC_SHA or static['changed_raw_sectors']!=EXPECTED_STATIC_CHANGED:
        raise SystemExit('static58 manifest baseline mismatch')

    static_extents=set()
    for a in static['assets']:
        static_extents |= extent_lbas(int(a['lba']),int(a['size']))
        got=sha_bytes(extract_asset(args.static_baseline,int(a['lba']),int(a['size'])))
        if got!=a['sha256']: raise SystemExit(f'static parent re-extraction fail: {a["name"]}')

    candidates={}; story_footprint=set()
    for a in story['assets']:
        p=args.candidate_dir/a['name']
        if not p.is_file() or p.stat().st_size!=a['size'] or sha_file(p)!=a['compiled_sha256']:
            raise SystemExit(f'exact story candidate missing or SHA mismatch: {a["name"]}')
        if sha_bytes(extract_asset(args.pristine,a['lba'],a['size']))!=a['source_sha256']:
            raise SystemExit(f'pristine story source re-extraction fail: {a["name"]}')
        candidates[a['name']]=p.read_bytes()
        footprint=extent_lbas(a['lba'],a['size'])
        if story_footprint & footprint: raise SystemExit(f'story LBA collision: {a["name"]}')
        story_footprint |= footprint
    if static_extents & story_footprint:
        raise SystemExit('static58 asset extent overlaps six-story footprint')

    static_changed=diff_lbas(args.pristine,args.static_baseline,mode1)
    if len(static_changed)!=EXPECTED_STATIC_CHANGED:
        raise SystemExit(f'static baseline changed-sector count mismatch: {len(static_changed)}')
    if set(static_changed)&story_footprint:
        raise SystemExit('static changed sectors overlap story footprint')

    shutil.copyfile(args.static_baseline,args.output)
    expected_write=[]; story_changed=[]
    try:
        with args.pristine.open('rb') as src,args.static_baseline.open('rb') as parent,args.output.open('r+b') as dst:
            for a in story['assets']:
                cand=candidates[a['name']]; remain=a['size']; pos=0; lba=a['lba']
                while remain:
                    src.seek(lba*RAW); pristine_raw=src.read(RAW)
                    parent.seek(lba*RAW); parent_raw=parent.read(RAW)
                    mode1.assert_mode1_sector(pristine_raw,f'pristine LBA {lba}')
                    mode1.assert_mode1_sector(parent_raw,f'parent LBA {lba}')
                    source_sha=sha_bytes(pristine_raw)
                    if sha_bytes(parent_raw)!=source_sha:
                        raise ValueError(f'Expected Write parent is not pristine at story LBA {lba}')
                    take=min(USER,remain)
                    user=bytearray(parent_raw[USER_OFF:USER_OFF+USER]); user[:take]=cand[pos:pos+take]
                    patched=patch_sector(mode1,parent_raw,bytes(user))
                    changed=patched!=parent_raw
                    expected_write.append({'asset':a['name'],'lba':lba,'source_sector_sha256':source_sha,
                                           'patched_sector_sha256':sha_bytes(patched),'candidate_user_bytes':take,'changed':changed})
                    if changed:
                        dst.seek(lba*RAW); dst.write(patched); story_changed.append(lba)
                    remain-=take; pos+=take; lba+=1
        if len(story_changed)!=EXPECTED_STORY_CHANGED:
            raise ValueError(f'story changed-sector count mismatch: {len(story_changed)}')
        if not set(story_changed)<=story_footprint:
            raise ValueError('story changed sector outside declared footprint')

        parent_delta=diff_lbas(args.static_baseline,args.output,mode1)
        if parent_delta!=story_changed:
            raise ValueError('output differs from static parent outside exact story delta')
        union_changed=diff_lbas(args.pristine,args.output,mode1)
        if len(union_changed)!=EXPECTED_UNION_CHANGED:
            raise ValueError(f'union changed-sector count mismatch: {len(union_changed)}')
        if set(union_changed)!=(set(static_changed)|set(story_changed)):
            raise ValueError('union changed-sector accounting mismatch')
        final_sha=sha_file(args.output)
        if final_sha!=EXPECTED_FINAL_SHA:
            raise ValueError(f'final Disc SHA mismatch: {final_sha}')

        static_reextract={}
        for a in static['assets']:
            got=sha_bytes(extract_asset(args.output,int(a['lba']),int(a['size'])))
            if got!=a['sha256']: raise ValueError(f'final static re-extraction fail: {a["name"]}')
            static_reextract[a['name']]=got
        story_reextract={}
        for a in story['assets']:
            got=sha_bytes(extract_asset(args.output,a['lba'],a['size']))
            if got!=a['compiled_sha256']: raise ValueError(f'final story re-extraction fail: {a["name"]}')
            story_reextract[a['name']]=got

        result={
            'batch':239,'status':'PASS_STATIC58_STORY6_EXACT_UNION_64_OF_64',
            'pristine_disc_sha256':story['source_disc']['sha256'],
            'static_parent_sha256':EXPECTED_STATIC_DISC_SHA,
            'output_disc_sha256':final_sha,
            'static_assets':'58/58 PASS','story_assets':'6/6 PASS','union_assets':'64/64 PASS',
            'static_changed_sectors':len(static_changed),'story_footprint_sectors':len(story_footprint),
            'story_changed_sectors':len(story_changed),'union_changed_sectors':len(union_changed),
            'lba_collisions':0,'unregistered_changed_sectors':0,'mode1_edc_ecc':'PASS',
            'expected_write_records':len(expected_write),
            'static_reextraction':static_reextract,'story_reextraction':story_reextract,
            'safety':{'guessed_bytes':False,'writes_outside_story_footprint':False,'full_disc_distributed':False},
        }
        args.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except Exception:
        args.output.unlink(missing_ok=True)
        raise

if __name__=='__main__':
    raise SystemExit(main())
