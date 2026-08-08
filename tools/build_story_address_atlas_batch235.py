#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
from collections import Counter,defaultdict
RAW=2352; USER_OFF=16; USER=2048; GLYPH_BYTES=128

def sha(b): return hashlib.sha256(b).hexdigest()
def raw_addr(lba,file_off):
    sec=file_off//USER; u=file_off%USER
    return {'iso_lba':lba+sec,'sector_user_offset':u,'raw_sector_offset':USER_OFF+u,'raw_disc_byte':(lba+sec)*RAW+USER_OFF+u}

def groups_from_ledger(obj):
    if 'target' in obj:
        name=Path(obj['target']).name
        return {name:{'meta':{'iso_path':obj['target'],'lba':obj['source']['lba'],'size':obj['source']['size'],'source_sha256':obj['source']['sha256'],'compiled_sha256':obj['compile']['compiled_sha256'],'font_slots_total':obj['font']['slots_total'],'font_slots_used':obj['font']['slots_used'],'font_slots_preserved':obj['font']['slots_preserved']},'records':obj['records']}}
    out={}
    for name,m in obj['files'].items():
        out[name]={'meta':{'iso_path':m['iso_path'],'lba':m['lba'],'size':m['source_size'],'source_sha256':m['source_sha256'],'compiled_sha256':m['compiled_sha256'],'font_slots_total':m['font_slots_total'],'font_slots_used':m['font_slots_used'],'font_slots_preserved':m['font_slots_preserved']},'records':[r for r in obj['records'] if r['file']==name]}
    return out

def locate_message_base(data, records):
    hashed=[r for r in records if r.get('source_record_sha256') and r.get('capacity_tokens') is not None and r.get('source_word_offset') is not None]
    if not hashed: raise ValueError('no record SHA anchors')
    anchors=sorted(hashed,key=lambda r:(r['capacity_tokens'], -r['source_word_offset']), reverse=True)[:12]
    candidates=Counter()
    for r in anchors:
        n=r['capacity_tokens']*2; target=r['source_record_sha256']; rel=r['source_word_offset']*2
        for off in range(0,len(data)-n+1,2):
            if sha(data[off:off+n])==target:
                base=off-rel
                if base>=0 and base%2==0: candidates[base]+=1
    if not candidates: raise ValueError('no SHA-derived message-base candidate')
    scored=[]
    for base,anchor_hits in candidates.items():
        ok=bad=0
        for r in hashed:
            off=base+r['source_word_offset']*2; n=r['capacity_tokens']*2
            if off<0 or off+n>len(data): bad+=1; continue
            if sha(data[off:off+n])==r['source_record_sha256']: ok+=1
            else: bad+=1
        scored.append((bad,-ok,-anchor_hits,base,ok))
    scored.sort(); bad,negok,nega,base,ok=scored[0]
    if bad: raise ValueError(f'message base not exact: best={base:#x} ok={ok} bad={bad}')
    return base,ok

def load_oracle(path):
    rows=[]
    with open(path,encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            try: slot=int(r['slot'])
            except: continue
            h=(r.get('glyph_sha256') or '').strip(); ch=(r.get('character') or '')
            if len(h)==64: rows.append((slot,ch,h))
    return rows

def locate_font_base(data,oracle,slots_total,min_hits=8):
    byhash=defaultdict(list)
    for slot,ch,h in oracle: byhash[h].append((slot,ch))
    votes=Counter(); evidence=defaultdict(list)
    for phase in range(GLYPH_BYTES):
        for off in range(phase,len(data)-GLYPH_BYTES+1,GLYPH_BYTES):
            h=sha(data[off:off+GLYPH_BYTES])
            for slot,ch in byhash.get(h,[]):
                base=off-slot*GLYPH_BYTES
                if base>=0 and base+slots_total*GLYPH_BYTES<=len(data):
                    votes[base]+=1; evidence[base].append({'slot':slot,'character':ch,'offset':off,'sha256':h})
    if not votes: return None
    base,hits=votes.most_common(1)[0]
    second=votes.most_common(2)[1][1] if len(votes)>1 else 0
    uniq=len({e['sha256'] for e in evidence[base]})
    if hits<min_hits or uniq<min_hits or hits==second: return {'status':'UNPROVEN','best_base':base,'hits':hits,'unique_hashes':uniq,'second_hits':second}
    return {'status':'VERIFIED_HASH_CONSENSUS','font_base':base,'font_end':base+slots_total*GLYPH_BYTES,'hits':hits,'unique_hashes':uniq,'second_hits':second,'evidence':evidence[base]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--ledger',action='append',required=True)
    ap.add_argument('--asset-dir',required=True)
    ap.add_argument('--glyph-oracle')
    ap.add_argument('--out',default='BATCH235_STORY_ADDRESS_ATLAS.json')
    a=ap.parse_args(); asset_dir=Path(a.asset_dir)
    oracle=load_oracle(a.glyph_oracle) if a.glyph_oracle else []
    allgroups={}
    for lp in a.ledger:
        obj=json.loads(Path(lp).read_text(encoding='utf-8')); allgroups.update(groups_from_ledger(obj))
    result={'batch':235,'policy':{'guessed_offsets':False,'record_address_basis':'SHA256 fixed-allocation scan','font_address_basis':'128-byte glyph SHA consensus only','raw_sector_geometry':'MODE1/2352 user bytes 16..2063'},'assets':{}}
    for name,g in allgroups.items():
        p=asset_dir/name
        if not p.is_file():
            result['assets'][name]={'status':'MISSING_SOURCE_ASSET','meta':g['meta']}; continue
        data=p.read_bytes(); m=g['meta']
        if len(data)!=m['size'] or sha(data)!=m['source_sha256']: raise SystemExit(f'{name}: source size/SHA mismatch')
        base,verified=locate_message_base(data,g['records'])
        records=[]
        for r in sorted(g['records'],key=lambda x:x['record']):
            off=base+r['source_word_offset']*2; n=r['capacity_tokens']*2
            rec={'record':r['record'],'type':r.get('record_type'),'word_offset':r['source_word_offset'],'capacity_tokens':r['capacity_tokens'],'file_byte_offset':off,'file_byte_end':off+n,'record_sha256':r.get('source_record_sha256'),'start_disc_address':raw_addr(m['lba'],off),'end_disc_address':raw_addr(m['lba'],off+n-1)}
            records.append(rec)
        font=locate_font_base(data,oracle,m['font_slots_total']) if oracle else {'status':'NO_ORACLE'}
        result['assets'][name]={'status':'PASS_EXACT_ADDRESS_ATLAS','meta':m,'message_base':base,'message_end':base+max(r['source_word_offset']+r['capacity_tokens'] for r in g['records'])*2,'records_verified_sha256':verified,'record_count':len(g['records']),'font':font,'records':records}
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':a.out,'assets':{k:{'status':v['status'],'record_count':v.get('record_count'),'message_base':v.get('message_base'),'font_status':v.get('font',{}).get('status')} for k,v in result['assets'].items()}},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
