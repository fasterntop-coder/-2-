#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, sys
from pathlib import Path

RAW=2352; USER_OFF=16; USER=2048; GLYPH_BYTES=128
HERE=Path(__file__).resolve().parent
DEFAULT_MANIFEST=HERE.parent/'manifests'/'CD1_STORY_EXACT_STRUCTURE_BATCH236.json'

def sha_bytes(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()

def load_ledgers(paths:list[Path])->dict[str,dict]:
    out={}
    for p in paths:
        obj=json.loads(p.read_text(encoding='utf-8'))
        if 'target' in obj:
            name=Path(obj['target']).name; out[name]={'records':obj['records']}
        elif 'files' in obj and 'records' in obj:
            for name in obj['files']:
                out[name]={'records':[r for r in obj['records'] if r.get('file')==name]}
    return out

def verify_formula(a:dict)->dict:
    font=a['size']-a['font_slots']*GLYPH_BYTES
    msg=font-a['allocated_tokens']*2
    table=msg-(4+a['record_count']*4)
    return {'font_start':font,'message_start':msg,'table_start':table,
            'match':font==a['font_start'] and msg==a['message_start'] and table==a['table_start']}

def verify_ledger(a:dict, records:list[dict])->dict:
    rows=sorted(records,key=lambda r:int(r['record']))
    contiguous=True; cursor=0; sha_anchors=0
    for i,r in enumerate(rows):
        if int(r['record'])!=i: contiguous=False
        if int(r['source_word_offset'])!=cursor: contiguous=False
        cursor += int(r['capacity_tokens'])
        if r.get('source_record_sha256'): sha_anchors+=1
    return {'record_count':len(rows),'allocated_tokens':cursor,'contiguous':contiguous,
            'record_count_match':len(rows)==a['record_count'],
            'allocated_tokens_match':cursor==a['allocated_tokens'],
            'sha_anchors':sha_anchors,
            'pass':contiguous and len(rows)==a['record_count'] and cursor==a['allocated_tokens']}

def import_mode1():
    repo=HERE.parent
    sys.path.insert(0,str(repo/'tools'))
    import mode1_2352 as m
    return m

def extract_asset(disc:Path,a:dict, mode1=None)->tuple[bytes,list[dict]]:
    out=bytearray(); remain=a['size']; lba=a['lba']; audit=[]
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW); raw=f.read(RAW)
            if len(raw)!=RAW: raise ValueError(f'short raw sector LBA {lba}')
            if mode1:
                v=mode1.verify_mode1_sector(raw)
                if not v['valid']: raise ValueError(f'EDC/ECC fail at LBA {lba}: {v}')
            take=min(USER,remain); out += raw[USER_OFF:USER_OFF+take]
            audit.append({'lba':lba,'raw_sha256':sha_bytes(raw),'take':take})
            remain-=take; lba+=1
    return bytes(out),audit

def verify_asset_records(data:bytes,a:dict,records:list[dict])->dict:
    ok=0; bad=[]
    for r in records:
        h=r.get('source_record_sha256')
        if not h: continue
        off=a['message_start']+int(r['source_word_offset'])*2
        n=int(r['capacity_tokens'])*2
        got=sha_bytes(data[off:off+n])
        if got==h: ok+=1
        else: bad.append({'record':r['record'],'offset':off,'expected':h,'actual':got})
    return {'verified':ok,'mismatches':bad,'pass':not bad}

def patch_sector(mode1, raw:bytes, user:bytes)->bytes:
    if len(raw)!=RAW or len(user)!=USER: raise ValueError('sector geometry')
    b=bytearray(raw); b[USER_OFF:USER_OFF+USER]=user
    b[0x810:0x814]=mode1.edc(bytes(b[:0x810])).to_bytes(4,'little')
    b[0x814:0x81C]=bytes(8)
    b[0x81C:0x8C8]=mode1._ecc_compute(bytes(b[0x0C:0x81C]),86,24,2,86)
    b[0x8C8:0x930]=mode1._ecc_compute(bytes(b[0x0C:0x8C8]),52,43,86,88)
    mode1.assert_mode1_sector(bytes(b),'patched sector')
    return bytes(b)

def integrate(disc:Path,candidate_dir:Path,mf:dict,out:Path)->dict:
    mode1=import_mode1()
    if disc.stat().st_size!=mf['source_disc']['size'] or sha_file(disc)!=mf['source_disc']['sha256']:
        raise ValueError('pristine Disc1 size/SHA mismatch')
    candidates={}
    for a in mf['assets']:
        p=candidate_dir/a['name']
        if not p.is_file(): raise ValueError(f'missing exact candidate: {a["name"]}')
        if p.stat().st_size!=a['size'] or sha_file(p)!=a['compiled_sha256']:
            raise ValueError(f'compiled candidate size/SHA mismatch: {a["name"]}')
        candidates[a['name']]=p.read_bytes()
    shutil.copyfile(disc,out)
    plan=[]; touched=set()
    try:
        with disc.open('rb') as src, out.open('r+b') as dst:
            for a in mf['assets']:
                cand=candidates[a['name']]; pos=0; remain=a['size']; lba=a['lba']
                while remain:
                    if lba in touched: raise ValueError(f'LBA collision {lba}')
                    touched.add(lba); src.seek(lba*RAW); raw=src.read(RAW)
                    mode1.assert_mode1_sector(raw,f'original LBA {lba}')
                    take=min(USER,remain); user=bytearray(raw[USER_OFF:USER_OFF+USER]); user[:take]=cand[pos:pos+take]
                    patched=patch_sector(mode1,raw,bytes(user))
                    expected=sha_bytes(raw); src.seek(lba*RAW); reread=src.read(RAW)
                    if sha_bytes(reread)!=expected: raise ValueError(f'Expected Write fail LBA {lba}')
                    dst.seek(lba*RAW); dst.write(patched)
                    plan.append({'asset':a['name'],'lba':lba,'original_sha256':expected,'patched_sha256':sha_bytes(patched),'user_bytes_replaced':take})
                    remain-=take; pos+=take; lba+=1
        changed=[]
        with disc.open('rb') as s, out.open('rb') as d:
            lba=0
            while True:
                x=s.read(RAW); y=d.read(RAW)
                if not x and not y: break
                if len(x)!=len(y): raise ValueError('output size mismatch')
                if x!=y: changed.append(lba)
                lba+=1
        if set(changed)!=touched: raise ValueError('unregistered changed sectors')
        reextract={}
        for a in mf['assets']:
            data,audit=extract_asset(out,a,mode1)
            h=sha_bytes(data)
            if h!=a['compiled_sha256']: raise ValueError(f're-extraction SHA fail {a["name"]}')
            reextract[a['name']]={'sha256':h,'sector_count':len(audit)}
        return {'status':'PASS_EXACT_SIX_STORY_INTEGRATION','source_disc_sha256':mf['source_disc']['sha256'],
                'output_disc_sha256':sha_file(out),'expected_write_plan':plan,
                'changed_sector_count':len(changed),'changed_lbas':changed,'other_changed_sectors':0,
                'lba_collisions':0,'mode1_edc_ecc':'PASS','reextraction':reextract}
    except Exception:
        out.unlink(missing_ok=True); raise

def main()->int:
    ap=argparse.ArgumentParser(description='Batch236 exact story structure / raw-sector integration gate')
    ap.add_argument('--manifest',type=Path,default=DEFAULT_MANIFEST)
    ap.add_argument('--ledger',type=Path,action='append',default=[])
    ap.add_argument('--asset-dir',type=Path)
    ap.add_argument('--disc',type=Path)
    ap.add_argument('--candidate-dir',type=Path)
    ap.add_argument('--output-disc',type=Path,default=Path('Sakura_Taisen_2_Disc1_B236_Story6_KO.bin'))
    ap.add_argument('--result',type=Path,default=Path('BATCH236_RESULT.json'))
    a=ap.parse_args(); mf=json.loads(a.manifest.read_text(encoding='utf-8'))
    ledgers=load_ledgers(a.ledger); result={'batch':236,'formula':{},'ledgers':{},'source_assets':{},'integration':None}
    all_formula=True
    for x in mf['assets']:
        f=verify_formula(x); result['formula'][x['name']]=f; all_formula &= f['match']
        if x['name'] in ledgers:
            lv=verify_ledger(x,ledgers[x['name']]['records']); result['ledgers'][x['name']]=lv
            if not lv['pass']: raise SystemExit(f'ledger contract fail: {x["name"]}')
    direct={x['name'] for x in mf['assets'] if x['structure_basis'].startswith('HISTORICAL_DIRECT')}
    if direct!={'SK0501.BIN','SK0502.BIN','SK0503.BIN'} or not all_formula: raise SystemExit('structure formula cross-validation fail')
    mode1=None
    if a.disc:
        mode1=import_mode1()
        if a.disc.stat().st_size!=mf['source_disc']['size'] or sha_file(a.disc)!=mf['source_disc']['sha256']:
            raise SystemExit('pristine Disc1 size/SHA mismatch')
    if a.asset_dir:
        for x in mf['assets']:
            p=a.asset_dir/x['name']
            if not p.is_file(): continue
            data=p.read_bytes()
            if len(data)!=x['size'] or sha_bytes(data)!=x['source_sha256']: raise SystemExit(f'source asset SHA mismatch: {x["name"]}')
            vr={'sha256':x['source_sha256'],'size':len(data)}
            if x['name'] in ledgers: vr['records']=verify_asset_records(data,x,ledgers[x['name']]['records'])
            result['source_assets'][x['name']]=vr
    if a.disc and a.candidate_dir:
        result['integration']=integrate(a.disc,a.candidate_dir,mf,a.output_disc)
    result['status']='PASS_STRUCTURE_CONTRACT' if result['integration'] is None else result['integration']['status']
    a.result.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'formula':result['formula'],'ledgers':result['ledgers'],'integration':result['integration'] and {'changed_sector_count':result['integration']['changed_sector_count'],'output_disc_sha256':result['integration']['output_disc_sha256']}},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
