#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any
from PIL import Image,ImageDraw,ImageFont
import importlib.util

# Paths are supplied by CLI. The sibling Batch329 builder provides the tested MES parser/map helpers.
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('b329', HERE/'build_batch329_psp_quality_replacements.py')
b329=importlib.util.module_from_spec(spec);spec.loader.exec_module(b329)
BASE: Path
LED: Path
OUT: Path
FONT: Path

SPECS={
 'EV03021.MES':{
  'lba':249816,'ledger':'R41_EV03020_EV03021_TRANSLATION.json',
  'source_sha256':'936ff18bfb18487a85eaded8dd892ed23c421d19a5c600192b3c6c10101d2786',
  'updates':{2:'그리고 제국화격단 때문에\n싫은 결혼을 한다니,\n이상하다고 생각했어……'},
  'reason':'Japanese source explicitly says 帝国華撃団; restore omitted 제국 while preserving the existing translation.'},
 'EV04001.MES':{
  'lba':250542,'ledger':'R41_BATCH51_TRANSLATION.json',
  'source_sha256':'d39b5c7559e93802eb61af162a48a0e9328acb2a0b04a3cf87107ea53f77566f',
  'updates':{4:'제국화격단 등장!'},
  'reason':'Exact source 帝国華撃団、参上！！ and PSP reference both contain 제국화격단; existing text omitted 제국.'},
 'EV32001.MES':{
  'lba':250584,'ledger':'R41_BATCH54_TRANSLATION.json',
  'source_sha256':'472c18655cd5f009aeaf1986eb24f59f6f4f77cd77683e58274b61b4927f3ee7',
  'updates':{4:'제국화격단 등장!'},
  'reason':'Exact source 帝国華撃団、参上！; existing text omitted 제국.'},
 'EV33001.MES':{
  'lba':251253,'ledger':'R41_BATCH55_TRANSLATION.json',
  'source_sha256':'95faefe8938cc5168da02c596d7faae65dabc1263064c10e8b0052de860be53c',
  'updates':{27:'대장, 늦었습니다.\n마리아 타치바나,\n지금 화조에 복귀합니다.'},
  'reason':'Japanese source explicitly says 花組に復帰; restore omitted 화조 while preserving current wording.'},
}

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def render_undotum14(ch:str)->bytes:
 font=ImageFont.truetype(str(FONT),14)
 im=Image.new('L',(16,16),0);ImageDraw.Draw(im).text((1,-4),ch,font=font,fill=255)
 vals=list(im.getdata());q=[min(15,(v+8)//17) for v in vals]
 return bytes((q[i]<<4)|q[i+1] for i in range(0,256,2))

def compile_one(fn:str,s:dict[str,Any])->dict[str,Any]:
 raw=(BASE/fn).read_bytes()
 if sha(raw)!=s['source_sha256']:raise ValueError(f'{fn}: source SHA mismatch')
 rows=b329.load_rows(LED/s['ledger'],fn)
 mp,rev,aligned=b329.build_char_map(raw,rows)
 offs,before=b329.parse_mes(raw)
 used={t for r in before for t in r['tokens'] if t<b329.FONT_SLOTS}
 buf=bytearray(raw);new_slots={};font_proof={}
 required=set(''.join(s['updates'].values()))-set(rev)-{'\n'}
 for ch in sorted(required):
  if not ('가'<=ch<='힣'):raise ValueError(f'{fn}: unmapped non-Hangul {ch!r}')
  exact=[(slot,c) for slot,c in mp.items() if '가'<=c<='힣' and raw[slot*128:(slot+1)*128]==render_undotum14(c)]
  if len(exact)<20:raise ValueError(f'{fn}: insufficient exact UnDotum14 raster proof ({len(exact)})')
  free=next((slot for slot in range(1,b329.FONT_SLOTS) if slot not in used and slot not in mp),None)
  if free is None:raise ValueError(f'{fn}: no free font slot')
  glyph=render_undotum14(ch)
  rev[ch]=free;mp[free]=ch;used.add(free);new_slots[ch]=free
  buf[free*128:(free+1)*128]=glyph
  font_proof[ch]={'slot':free,'target_existing_exact_raster_samples':len(exact),'renderer':'UnDotum 14px (1,-4), 4bpp rounded grayscale'}
 changed=[]
 for ri,text in s['updates'].items():
  r=before[ri];toks=b329.encode_text(text,rev)
  payload=r['metadata']+b''.join(t.to_bytes(2,'big') for t in toks)
  cap=r['end']-r['start']
  if len(payload)>cap:raise ValueError(f'{fn} rec {ri}: overflow {len(payload)}/{cap}')
  payload+=bytes(cap-len(payload));buf[r['start']:r['end']]=payload;changed.append(ri)
 out=bytes(buf);outoffs,after=b329.parse_mes(out)
 if offs!=outoffs:raise ValueError(f'{fn}: offset table changed')
 tb=4+4*len(offs)
 if raw[b329.MSG_START:b329.MSG_START+tb]!=out[b329.MSG_START:b329.MSG_START+tb]:raise ValueError(f'{fn}: table bytes changed')
 if raw[b329.MSG_END:]!=out[b329.MSG_END:]:raise ValueError(f'{fn}: execution tail changed')
 for a,b in zip(before,after):
  if a['metadata']!=b['metadata']:raise ValueError(f'{fn}: metadata changed rec {a["index"]}')
  if a['index'] not in changed and a['bytes']!=b['bytes']:raise ValueError(f'{fn}: untouched record changed {a["index"]}')
 allowed=set()
 for slot in new_slots.values():allowed.update(range(slot*128,(slot+1)*128))
 fdiff={i for i,(a,b) in enumerate(zip(raw[:b329.MSG_START],out[:b329.MSG_START])) if a!=b}
 if not fdiff.issubset(allowed):raise ValueError(f'{fn}: font changed outside new slots')
 decoded={}
 for ri,text in s['updates'].items():
  got=b329.reverse_decode(after[ri]['tokens'],mp)
  if got!=text:raise ValueError(f'{fn}: reverse mismatch rec {ri}: {got!r}')
  decoded[str(ri)]=got
 op=OUT/'SAKURA2'/fn;op.parent.mkdir(parents=True,exist_ok=True);op.write_bytes(out)
 return {'iso_path':f'SAKURA2/{fn}','lba':s['lba'],'size':len(out),'source_sha256':sha(raw),'replacement_sha256':sha(out),'changed_records':changed,'reverse_decoded':decoded,'new_font_slots':new_slots,'font_proof':font_proof,'offset_table_byte_exact':True,'all_record_metadata_byte_exact':True,'execution_tail_byte_exact':True,'untouched_records_byte_exact':True,'font_changes_limited_to_new_slots':True,'reason':s['reason']}

def main():
 import argparse
 global BASE,LED,OUT,FONT
 ap=argparse.ArgumentParser(description='Build Batch331 high-confidence canonical terminology repairs')
 ap.add_argument('--base-dir',type=Path,required=True,help='Directory containing exact current compiled source MES files')
 ap.add_argument('--ledger-dir',type=Path,required=True,help='Directory containing current translation JSON ledgers')
 ap.add_argument('--font',type=Path,required=True,help='UnDotum.ttf used by Batch51/54 Event MES lineage')
 ap.add_argument('--out-dir',type=Path,required=True)
 args=ap.parse_args();BASE=args.base_dir;LED=args.ledger_dir;OUT=args.out_dir;FONT=args.font
 files={fn:compile_one(fn,s) for fn,s in SPECS.items()}
 report={'format':'ST2-CD1-BATCH331-PSP-CANONICAL-TERMINOLOGY-REPAIRS-v1','batch':331,'status':'PASS_ACTUAL_REPLACEMENT_MES_4_FILES_4_RECORDS','scope':{'replacement_files':4,'changed_records':4},'files':files,'guessed_bytes':0,'parent_disc_write_performed':False}
 (OUT/'BATCH331_PSP_CANONICAL_TERMINOLOGY_REPAIRS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
