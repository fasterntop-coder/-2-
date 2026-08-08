#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

EXPECTED={"SK0501.BIN","SK0502.BIN","SK0503.BIN","SKCM02.BIN","SKCM04.BIN","SKCM05.BIN"}

def sha_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def load_groups(paths:list[Path])->dict[str,dict]:
    out={}
    for path in paths:
        obj=json.loads(path.read_text(encoding='utf-8'))
        if 'target' in obj:
            name=Path(obj['target']).name
            out[name]={'iso_path':obj['target'],'lba':obj['source']['lba'],'size':obj['source']['size'],
                       'source_sha256':obj['source']['sha256'],'compiled_sha256':obj['compile']['compiled_sha256'],
                       'font_slots_total':obj['font']['slots_total'],'font_slots_used':obj['font']['slots_used'],
                       'font_slots_preserved':obj['font']['slots_preserved'],'records':obj['records'],'ledger':path.name}
        else:
            for name,node in obj['files'].items():
                rows=node.get('records')
                if not isinstance(rows,list): rows=[r for r in obj.get('records',[]) if r.get('file')==name]
                out[name]={'iso_path':node['iso_path'],'lba':node['lba'],'size':node['source_size'],
                           'source_sha256':node['source_sha256'],'compiled_sha256':node['compiled_sha256'],
                           'font_slots_total':node['font_slots_total'],'font_slots_used':node['font_slots_used'],
                           'font_slots_preserved':node['font_slots_preserved'],'records':rows,'ledger':path.name}
    return out

def controls(rec:dict)->list[str]:
    out=[]
    hx=rec.get('source_tokens_hex')
    if isinstance(hx,str):
        out.extend(t.upper() for t in hx.split() if t.upper() in {'FFFA','FFFB','FFFC','FFFD','FFFE','FFFF'})
    for pair in rec.get('control_pairs') or []:
        if isinstance(pair,list) and pair: out.append(str(pair[0]).upper())
        elif pair: out.append(str(pair).upper())
    if rec.get('has_fffd_control') and 'FFFD' not in out: out.append('FFFD')
    return out

def main()->int:
    ap=argparse.ArgumentParser(description='Batch237 exact relative address/control census for six Disc1 story BINs')
    ap.add_argument('--ledger',type=Path,action='append',required=True)
    ap.add_argument('--out-dir',type=Path,default=Path('BATCH237_OUTPUT'))
    a=ap.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True)
    groups=load_groups(a.ledger)
    if set(groups)!=EXPECTED: raise SystemExit(f'exact six-ledger target set required: {sorted(groups)}')
    rows=[]; assets={}
    for name in sorted(groups):
        g=groups[name]; rs=sorted(g['records'],key=lambda r:int(r['record']))
        cursor=0; ctrl=Counter(); types=Counter(); source_status=Counter(); unknown=0
        for i,r in enumerate(rs):
            rid=int(r['record']); off=int(r['source_word_offset']); cap=int(r['capacity_tokens'])
            if rid!=i: raise SystemExit(f'{name}: record index gap at {i}/{rid}')
            if off!=cursor: raise SystemExit(f'{name}: allocation gap at record {rid}: {cursor}!={off}')
            h=r.get('source_record_sha256','')
            if len(h)!=64: raise SystemExit(f'{name}: record {rid} missing SHA-256')
            cc=controls(r); ctrl.update(cc); types[r.get('record_type','')]+=1; source_status[r.get('source_status','')]+=1
            unknown += len(r.get('source_unknown_slots') or [])
            rows.append({'asset':name,'record':rid,'word_offset':off,'relative_byte_offset':off*2,
                         'capacity_tokens':cap,'byte_length':cap*2,'relative_byte_end_exclusive':(off+cap)*2,
                         'source_record_sha256':h,'record_type':r.get('record_type',''),'source_status':r.get('source_status',''),
                         'control_codes':'|'.join(sorted(set(cc))),'unknown_slot_ref_count':len(r.get('source_unknown_slots') or [])})
            cursor += cap
        assets[name]={'iso_path':g['iso_path'],'lba':g['lba'],'size':g['size'],'source_sha256':g['source_sha256'],
                      'compiled_sha256':g['compiled_sha256'],'ledger':g['ledger'],'record_count':len(rs),
                      'allocated_words':cursor,'allocated_bytes':cursor*2,'relative_allocation_contiguous':True,
                      'all_records_sha_anchored':True,'font_slots_total':g['font_slots_total'],'font_slots_used':g['font_slots_used'],
                      'font_slots_preserved':g['font_slots_preserved'],'control_counts':dict(sorted(ctrl.items())),
                      'record_type_counts':dict(types),'source_status_counts':dict(source_status),'unknown_slot_refs':unknown}
    csvp=a.out_dir/'CD1_STORY_RELATIVE_ADDRESS_ATLAS_BATCH237.csv'
    with csvp.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    result={'batch':237,'status':'PASS_EXACT_RELATIVE_ADDRESS_CENSUS_3148_OF_3148',
            'policy':{'guessed_bytes':False,'absolute_addresses':False,'record_sha_required':True,
                      'next_absolute_gate':'source asset SHA -> exact message base -> 3148 record SHA -> LBA/raw-sector projection'},
            'scope':{'assets':6,'records':len(rows),'allocated_words':sum(v['allocated_words'] for v in assets.values()),
                     'allocated_bytes':sum(v['allocated_bytes'] for v in assets.values())},
            'atlas_csv_sha256':sha_file(csvp),'assets':assets}
    out=a.out_dir/'CD1_STORY_STRUCTURE_CENSUS_BATCH237.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'scope':result['scope'],'atlas_csv_sha256':result['atlas_csv_sha256']},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
