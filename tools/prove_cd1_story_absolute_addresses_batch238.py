#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

RAW=2352
USER_OFF=16
USER=2048
GLYPH_BYTES=128
HERE=Path(__file__).resolve().parent
DEFAULT_MANIFEST=HERE.parent/'manifests'/'CD1_STORY_EXACT_STRUCTURE_BATCH236.json'


def sha_bytes(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(8*1024*1024):
            h.update(chunk)
    return h.hexdigest()


def load_ledgers(paths:list[Path])->dict[str,list[dict]]:
    out={}
    for path in paths:
        obj=json.loads(path.read_text(encoding='utf-8'))
        if 'target' in obj:
            out[Path(obj['target']).name]=obj['records']
            continue
        for name,node in obj.get('files',{}).items():
            rows=node.get('records')
            if not isinstance(rows,list):
                rows=[r for r in obj.get('records',[]) if r.get('file')==name]
            out[name]=rows
    return out


def import_mode1():
    sys.path.insert(0,str(HERE))
    import mode1_2352 as mode1
    return mode1


def project(lba:int,file_offset:int)->dict:
    sector=lba+file_offset//USER
    user=file_offset%USER
    return {
        'iso_lba':sector,
        'sector_user_offset':user,
        'raw_sector_offset':USER_OFF+user,
        'raw_disc_byte':sector*RAW+USER_OFF+user,
    }


def extract_asset(disc:Path, asset:dict, mode1)->tuple[bytes,list[dict]]:
    out=bytearray(); audits=[]; remain=asset['size']; lba=asset['lba']
    with disc.open('rb') as f:
        while remain:
            f.seek(lba*RAW); raw=f.read(RAW)
            if len(raw)!=RAW:
                raise ValueError(f'{asset["name"]}: short sector at LBA {lba}')
            check=mode1.verify_mode1_sector(raw)
            if not check['valid']:
                raise ValueError(f'{asset["name"]}: MODE1 EDC/ECC failure at LBA {lba}: {check}')
            take=min(USER,remain)
            out.extend(raw[USER_OFF:USER_OFF+take])
            audits.append({'lba':lba,'raw_sha256':sha_bytes(raw),'user_bytes':take})
            remain-=take; lba+=1
    return bytes(out),audits


def unique_record_prefix(blob:bytes,target_sha:str)->int:
    matches=[]
    for end in range(2,len(blob)+1,2):
        if blob[end-2:end]!=b'\xff\xff':
            continue
        if sha_bytes(blob[:end])==target_sha:
            matches.append(end)
    if len(matches)!=1:
        raise ValueError(f'record SHA does not select one FFFF-terminated prefix: matches={matches}')
    if any(blob[matches[0]:]):
        raise ValueError('bytes after exact record prefix are not zero padding')
    return matches[0]


def verify_structure(data:bytes,asset:dict,records:list[dict])->tuple[list[dict],dict]:
    expected_font=asset['size']-asset['font_slots']*GLYPH_BYTES
    expected_message=expected_font-asset['allocated_tokens']*2
    expected_table=expected_message-(4+asset['record_count']*4)
    if (expected_table,expected_message,expected_font)!=(asset['table_start'],asset['message_start'],asset['font_start']):
        raise ValueError(f'{asset["name"]}: frozen structure formula mismatch')

    rows=sorted(records,key=lambda r:int(r['record']))
    if len(rows)!=asset['record_count']:
        raise ValueError(f'{asset["name"]}: record count mismatch')
    count=int.from_bytes(data[asset['table_start']:asset['table_start']+4],'big')
    if count!=asset['record_count']+1:
        raise ValueError(f'{asset["name"]}: table count {count} != records+1')
    ptrs=[int.from_bytes(data[asset['table_start']+4+i*4:asset['table_start']+8+i*4],'big') for i in range(asset['record_count'])]
    ledger_ptrs=[int(r['source_word_offset']) for r in rows]
    if ptrs!=ledger_ptrs:
        raise ValueError(f'{asset["name"]}: pointer table != historical source_word_offset ledger')

    atlas=[]; trimmed=[]; cursor=0
    for index,r in enumerate(rows):
        rid=int(r['record']); word_off=int(r['source_word_offset']); cap=int(r['capacity_tokens'])
        if rid!=index or word_off!=cursor:
            raise ValueError(f'{asset["name"]}: record sequence/allocation gap at record {rid}')
        file_off=asset['message_start']+word_off*2
        alloc_bytes=cap*2
        blob=data[file_off:file_off+alloc_bytes]
        if len(blob)!=alloc_bytes:
            raise ValueError(f'{asset["name"]}: short record allocation {rid}')
        effective=unique_record_prefix(blob,r['source_record_sha256'])
        zero_pad=alloc_bytes-effective
        if zero_pad:
            trimmed.append({'record':rid,'allocation_bytes':alloc_bytes,'effective_bytes':effective,'trailing_zero_pad_bytes':zero_pad})
        start=project(asset['lba'],file_off)
        end=project(asset['lba'],file_off+effective-1)
        atlas.append({
            'asset':asset['name'],'record':rid,'table_word_offset':word_off,
            'file_byte_offset':file_off,'allocation_bytes':alloc_bytes,
            'effective_record_bytes':effective,'trailing_zero_pad_bytes':zero_pad,
            'source_record_sha256':r['source_record_sha256'],
            'iso_lba':start['iso_lba'],'sector_user_offset':start['sector_user_offset'],
            'raw_sector_offset':start['raw_sector_offset'],'raw_disc_byte':start['raw_disc_byte'],
            'end_iso_lba':end['iso_lba'],'end_sector_user_offset':end['sector_user_offset'],
            'end_raw_disc_byte':end['raw_disc_byte'],
        })
        cursor+=cap
    if cursor!=asset['allocated_tokens']:
        raise ValueError(f'{asset["name"]}: final allocation mismatch')
    proof={
        'table_start':asset['table_start'],'message_start':asset['message_start'],'font_start':asset['font_start'],
        'table_count':count,'pointer_entries_verified':len(ptrs),'record_sha_verified':len(rows),
        'allocated_tokens':cursor,'trailing_zero_pad_records':trimmed,
    }
    return atlas,proof


def write_csv(path:Path,rows:list[dict])->str:
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return sha_file(path)


def main()->int:
    ap=argparse.ArgumentParser(description='Batch238 exact pristine-disc story address / glyph-slot proof')
    ap.add_argument('--disc',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,default=DEFAULT_MANIFEST)
    ap.add_argument('--ledger',type=Path,action='append',required=True)
    ap.add_argument('--out-dir',type=Path,default=Path('BATCH238_OUTPUT'))
    args=ap.parse_args(); args.out_dir.mkdir(parents=True,exist_ok=True)
    mf=json.loads(args.manifest.read_text(encoding='utf-8'))
    if args.disc.stat().st_size!=mf['source_disc']['size'] or sha_file(args.disc)!=mf['source_disc']['sha256']:
        raise SystemExit('pristine Disc1 size/SHA mismatch')
    ledgers=load_ledgers(args.ledger)
    expected={a['name'] for a in mf['assets']}
    if set(ledgers)!=expected:
        raise SystemExit(f'exact six-ledger set required: got={sorted(ledgers)}')
    mode1=import_mode1()
    address_rows=[]; glyph_rows=[]; proofs={}; sector_lbas=[]
    for asset in mf['assets']:
        data,audit=extract_asset(args.disc,asset,mode1)
        if len(data)!=asset['size'] or sha_bytes(data)!=asset['source_sha256']:
            raise SystemExit(f'{asset["name"]}: source asset size/SHA mismatch')
        rows,proof=verify_structure(data,asset,ledgers[asset['name']])
        address_rows.extend(rows)
        proof['source_sha256']=asset['source_sha256']
        proof['source_sector_count']=len(audit)
        proofs[asset['name']]=proof
        sector_lbas.extend(x['lba'] for x in audit)
        for slot in range(asset['font_slots']):
            off=asset['font_start']+slot*GLYPH_BYTES
            pos=project(asset['lba'],off)
            glyph=data[off:off+GLYPH_BYTES]
            if len(glyph)!=GLYPH_BYTES:
                raise SystemExit(f'{asset["name"]}: short glyph slot {slot}')
            glyph_rows.append({
                'asset':asset['name'],'slot':slot,'file_byte_offset':off,
                'iso_lba':pos['iso_lba'],'sector_user_offset':pos['sector_user_offset'],
                'raw_sector_offset':pos['raw_sector_offset'],'raw_disc_byte':pos['raw_disc_byte'],
                'glyph_sha256':sha_bytes(glyph),
            })
    if len(sector_lbas)!=len(set(sector_lbas)):
        raise SystemExit('source asset LBA collision')
    address_csv=args.out_dir/'CD1_STORY_ABSOLUTE_ADDRESS_ATLAS_BATCH238.csv'
    glyph_csv=args.out_dir/'CD1_STORY_GLYPH_SLOT_ADDRESS_ATLAS_BATCH238.csv'
    address_sha=write_csv(address_csv,address_rows)
    glyph_sha=write_csv(glyph_csv,glyph_rows)
    result={
        'batch':238,'status':'PASS_PRISTINE_DISC_ABSOLUTE_STORY_ADDRESS_PROOF',
        'source_disc':{'size':args.disc.stat().st_size,'sha256':mf['source_disc']['sha256']},
        'scope':{'assets':len(mf['assets']),'records':len(address_rows),'glyph_slots':len(glyph_rows),'source_sectors':len(sector_lbas)},
        'mode1_edc_ecc':{'checked_sectors':len(sector_lbas),'failed':0,'status':'PASS'},
        'lba_collisions':0,
        'address_atlas':{'file':address_csv.name,'sha256':address_sha},
        'glyph_slot_atlas':{'file':glyph_csv.name,'sha256':glyph_sha},
        'assets':proofs,
        'safety':{'guessed_addresses':False,'guessed_bytes':False,'record_address_acceptance':'exact table pointer + exact FFFF-terminated source-record SHA','disc_write_performed':False},
    }
    rp=args.out_dir/'BATCH238_RESULT.json'
    rp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
