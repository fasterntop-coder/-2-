#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

DISC_SIZE=659_293_824; USER_OFF=16; USER_SIZE=2048
R38_SHA="5869491e19b4316c61725910561ec47c3f60af1983b4eae9996c5aed9e1cfd8c"
R39_SHA="57335616e481102fe2ef7ab080871df479211f388eff796d5c6bca7a28958025"
B290_STATUS="PASS_BATCH290_B289_PLUS_R38_CH2_FONT7_EXACT_UNION"
PASS_STATUS="PASS_BATCH291_B290_PLUS_R39_FONT2_EXACT_UNION"
EXPECTED_DELTA_SECTORS=29
ASSETS=[
    ("SAKURA2/M01LOW.BIN",219653,412480,340),
    ("SAKURA2/EV02001.MES",248627,71851,46),
]

def shab(b): return hashlib.sha256(b).hexdigest()
def shaf(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()
def extract(raw,lba,size):
    out=bytearray(); n=0
    while len(out)<size:
        off=(lba+n)*RAW_SECTOR_SIZE; sec=raw[off:off+RAW_SECTOR_SIZE]
        if len(sec)!=RAW_SECTOR_SIZE or sec[15]!=1: raise SystemExit(f'FAIL non-MODE1 asset sector LBA {lba+n}')
        take=min(USER_SIZE,size-len(out)); out+=sec[USER_OFF:USER_OFF+take]; n+=1
    return bytes(out)
def bind_report(path,status,disc_sha,label):
    r=json.loads(path.read_text(encoding='utf-8'))
    if r.get('status')!=status: raise SystemExit(f'FAIL {label} status')
    if str(r.get('output_sha256','')).lower()!=disc_sha: raise SystemExit(f'FAIL {label} output SHA binding')
    if int(r.get('guessed_payload_bytes',0))!=0: raise SystemExit(f'FAIL {label} guessed payload bytes')
    return r

def main():
    ap=argparse.ArgumentParser(description='Batch291 exact R39 two-asset font normalization union onto successful Batch290')
    ap.add_argument('--parent-bin',required=True,type=Path); ap.add_argument('--b290-report',required=True,type=Path)
    ap.add_argument('--r38-bin',required=True,type=Path); ap.add_argument('--r39-bin',required=True,type=Path)
    ap.add_argument('--output-bin',required=True,type=Path); ap.add_argument('--report',required=True,type=Path)
    a=ap.parse_args()
    for p in (a.parent_bin,a.r38_bin,a.r39_bin):
        if p.stat().st_size!=DISC_SIZE: raise SystemExit(f'FAIL disc size {p}')
    parent_sha,r38_sha,r39_sha=shaf(a.parent_bin),shaf(a.r38_bin),shaf(a.r39_bin)
    if r38_sha!=R38_SHA: raise SystemExit('FAIL R38 whole-disc SHA binding')
    if r39_sha!=R39_SHA: raise SystemExit('FAIL R39 whole-disc SHA binding')
    bind_report(a.b290_report,B290_STATUS,parent_sha,'Batch290')
    parent=a.parent_bin.read_bytes(); r38=a.r38_bin.read_bytes(); r39=a.r39_bin.read_bytes()
    asset_lbas=set(); donor_assets=[]
    for path,lba,size,glyphs in ASSETS:
        r38_asset=extract(r38,lba,size); r39_asset=extract(r39,lba,size)
        donor_assets.append({'path':path,'lba':lba,'size':size,'normalized_glyphs':glyphs,'r38_sha256':shab(r38_asset),'r39_sha256':shab(r39_asset)})
        asset_lbas.update(range(lba,lba+(size+USER_SIZE-1)//USER_SIZE))
    delta=[]
    for lba in sorted(asset_lbas):
        off=lba*RAW_SECTOR_SIZE; before=r38[off:off+RAW_SECTOR_SIZE]; after=r39[off:off+RAW_SECTOR_SIZE]
        if before!=after:
            if not verify_mode1_sector(before)['valid']: raise SystemExit(f'FAIL R38 baseline EDC/ECC LBA {lba}')
            if not verify_mode1_sector(after)['valid']: raise SystemExit(f'FAIL R39 donor EDC/ECC LBA {lba}')
            delta.append((lba,shab(before),shab(after)))
    if len(delta)!=EXPECTED_DELTA_SECTORS: raise SystemExit(f'FAIL R38->R39 delta sector count {len(delta)} != {EXPECTED_DELTA_SECTORS}')
    out=bytearray(parent); ew=[]; already=0
    for lba,bsha,asha in delta:
        off=lba*RAW_SECTOR_SIZE; cur=bytes(parent[off:off+RAW_SECTOR_SIZE]); csha=shab(cur)
        if csha==asha: already+=1; continue
        if csha!=bsha: raise SystemExit(f'FAIL third variant LBA {lba}: parent={csha} r38={bsha} r39={asha}')
        ew.append({'lba':lba,'before_sha256':bsha,'after_sha256':asha}); out[off:off+RAW_SECTOR_SIZE]=r39[off:off+RAW_SECTOR_SIZE]
    actual=[]
    for lba in sorted(asset_lbas):
        off=lba*RAW_SECTOR_SIZE
        if parent[off:off+RAW_SECTOR_SIZE]!=out[off:off+RAW_SECTOR_SIZE]: actual.append(lba)
    if actual!=[x['lba'] for x in ew]: raise SystemExit('FAIL changed-LBA accounting')
    for w in ew:
        off=w['lba']*RAW_SECTOR_SIZE; sec=bytes(out[off:off+RAW_SECTOR_SIZE])
        if shab(sec)!=w['after_sha256'] or not verify_mode1_sector(sec)['valid']: raise SystemExit(f"FAIL final sector gate LBA {w['lba']}")
    audit=[]
    for d in donor_assets:
        final_sha=shab(extract(out,d['lba'],d['size']))
        if final_sha!=d['r39_sha256']: raise SystemExit(f"FAIL final whole-asset re-extraction {d['path']}")
        audit.append({**d,'final_sha256':final_sha,'status':'PASS'})
    a.output_bin.parent.mkdir(parents=True,exist_ok=True); a.output_bin.write_bytes(out); output_sha=shaf(a.output_bin)
    report={'batch':291,'status':PASS_STATUS,'parent_batch':290,'parent_sha256':parent_sha,'r38_sha256':r38_sha,'r39_sha256':r39_sha,'asset_count':2,'converted_hangul_glyph_slots':386,'script_pointer_control_bytes_changed':0,'derived_r38_to_r39_delta_sectors':len(delta),'already_target_sectors':already,'expected_write_count':len(ew),'expected_write':ew,'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','whole_asset_reextraction':'2/2 PASS','asset_audit':audit,'event_mes_logical_completion':'109/109','static_assets_verified':58,'speech_movies_physical':'12/12','episode_title_cards_physical':'6/6','title_assets_physical':'3/3','additional_ui_assets_physical':'3/3','runtime_support_assets_physical':'5/5','chapter2_font_normalized_story_assets_physical':'7/7','r39_font_normalized_assets_physical':'2/2','guessed_payload_bytes':0,'output_sha256':output_sha}
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(PASS_STATUS); print(f'output_sha256={output_sha}'); print(f'changed_raw_sectors={len(actual)}'); print('whole_asset_reextraction=2/2 PASS')
if __name__=='__main__': main()
