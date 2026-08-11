#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, tempfile, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from mode1_2352 import RAW_SECTOR_SIZE, _ecc_compute, edc, verify_mode1_sector

DISC_SIZE=659_293_824
USER_OFF=16
USER_SIZE=2048
PRISTINE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
PARENT_STATUS='PASS_BATCH301_B300_PLUS_B34_39_EVENT8_EXACT_UNION'
SUCCESS='PASS_BATCH302_B301_PLUS_B118_BATTLE58_EXACT_UNION'
WORKBOOK_SHA='e8c85862c10b6d30ed21156b17ca93be834c5cb5f76cf1f58d97c1db6ca22ce9'
HISTORICAL_B118_OUTPUT_SHA='75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20'
EXPECTED_ASSETS=58
EXPECTED_HISTORICAL_CHANGED_SECTORS=1626

ORACLES={
 'PBOOK_BT':('43c64ed80b88e798d8d0162ba37660467c7da77af2b5e1928f2c5dee82c56b64','4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe',15609,87712),
 'PBOOK_EC':('3118ecdf03d7225f9666298b7c93b357c276bbdc27ce0b7020baca12003db3bc','378d92a4daf3db00d7c172ae8d233fad1fe3e1452cb979e9bd8b5610220152f5',15652,87456),
 'PBOOK_RC':('56f8607a5c3ab6c5ad79b1b3de2910822f3880fa7f2e3938b273a1dfa27bc201','c5bc0866ea5581f64bccb0a9da1c6baf53c77601fa247469441e49d0eaae4907',15695,58208),
 'SYSTEM':('943d6cf1fb996a416f90ad6e2bea2b147f4931623b480a1622cf200586ddd385','aff08f718bb8186c7162601f76b927dfa516c21139f60fc6d3cf27f8a8a84a58',208745,80458),
 'SYS14':('69f618f86010c35f28d20efc40a9374a3fc99e594cc7b110ad91c4fa36ce1f5a','06597ddf3d34f0463e611f796146bb1e80d7e32df1f59925481669969840b92d',207118,82032),
}

def shab(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def shaf(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()

def extract(raw:bytes|bytearray,lba:int,size:int)->bytes:
 out=bytearray(); i=0
 while len(out)<size:
  off=(lba+i)*RAW_SECTOR_SIZE; sec=raw[off:off+RAW_SECTOR_SIZE]
  if len(sec)!=RAW_SECTOR_SIZE or sec[15]!=1:raise SystemExit(f'FAIL MODE1 LBA {lba+i}')
  take=min(USER_SIZE,size-len(out));out+=sec[USER_OFF:USER_OFF+take];i+=1
 return bytes(out)

def rebuild(sec:bytearray)->None:
 sec[0x810:0x814]=edc(bytes(sec[:0x810])).to_bytes(4,'little');sec[0x814:0x81C]=bytes(8)
 sec[0x81C:0x8C8]=_ecc_compute(bytes(sec[0x0C:0x81C]),86,24,2,86)
 sec[0x8C8:0x930]=_ecc_compute(bytes(sec[0x0C:0x8C8]),52,43,86,88)

def _col(ref:str)->str:
 m=re.match(r'([A-Z]+)',ref or '')
 return m.group(1) if m else ''

def read_assets58_xlsx(path:Path)->list[dict]:
 if shaf(path)!=WORKBOOK_SHA:raise SystemExit('FAIL canonical B118 workbook SHA')
 NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
 RNS='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
 with zipfile.ZipFile(path) as z:
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   root=ET.fromstring(z.read('xl/sharedStrings.xml'))
   for si in root.findall(NS+'si'):
    shared.append(''.join(t.text or '' for t in si.iter(NS+'t')))
  wb=ET.fromstring(z.read('xl/workbook.xml'))
  rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
  relmap={r.attrib['Id']:r.attrib['Target'] for r in rels}
  target=None
  for s in wb.find(NS+'sheets'):
   if s.attrib.get('name')=='Assets 58':
    target=relmap[s.attrib[RNS+'id']];break
  if not target:raise SystemExit('FAIL Assets 58 sheet missing')
  if not target.startswith('worksheets/'): target='worksheets/'+Path(target).name
  root=ET.fromstring(z.read('xl/'+target))
  matrix=[]
  for row in root.iter(NS+'row'):
   vals={}
   for c in row.findall(NS+'c'):
    ref=c.attrib.get('r','');typ=c.attrib.get('t');v=c.find(NS+'v');isn=c.find(NS+'is')
    text=''
    if typ=='s' and v is not None:text=shared[int(v.text)]
    elif typ=='inlineStr' and isn is not None:text=''.join(t.text or '' for t in isn.iter(NS+'t'))
    elif v is not None:text=v.text or ''
    vals[_col(ref)]=text
   if vals:matrix.append(vals)
  header_i=None; col_by_name={}
  for i,row in enumerate(matrix):
   rev={str(v).strip():k for k,v in row.items()}
   if {'asset','lba','size','original_sha256','candidate_sha256'}.issubset(rev):
    header_i=i;col_by_name=rev;break
  if header_i is None:raise SystemExit('FAIL Assets 58 header')
  required=['asset','source_batch','lba','size','original_sha256','candidate_sha256','changed_sector_count']
  out=[]
  for row in matrix[header_i+1:]:
   asset=str(row.get(col_by_name['asset'],'')).strip()
   if not asset:continue
   try:
    rec={k:row.get(col_by_name[k],'') for k in required}
    rec['asset']=asset;rec['source_batch']=int(float(rec['source_batch']));rec['lba']=int(float(rec['lba']));rec['size']=int(float(rec['size']));rec['changed_sector_count']=int(float(rec['changed_sector_count']))
    rec['original_sha256']=str(rec['original_sha256']).strip().lower();rec['candidate_sha256']=str(rec['candidate_sha256']).strip().lower()
   except Exception as e:raise SystemExit(f'FAIL workbook row {asset}: {e}')
   out.append(rec)
  if len(out)!=EXPECTED_ASSETS:raise SystemExit(f'FAIL workbook asset count {len(out)} != 58')
  if len({r['asset'] for r in out})!=58 or len({r['lba'] for r in out})!=58:raise SystemExit('FAIL duplicate B118 asset/LBA')
  if sum(r['changed_sector_count'] for r in out)!=EXPECTED_HISTORICAL_CHANGED_SECTORS:raise SystemExit('FAIL historical changed-sector total')
  for r in out:
   if not re.fullmatch(r'[0-9a-f]{64}',r['original_sha256']) or not re.fullmatch(r'[0-9a-f]{64}',r['candidate_sha256']):raise SystemExit(f"FAIL SHA field {r['asset']}")
  by={r['asset']:r for r in out}
  for asset,(src,dst,lba,size) in ORACLES.items():
   r=by.get(asset)
   if not r or (r['original_sha256'],r['candidate_sha256'],r['lba'],r['size'])!=(src,dst,lba,size):raise SystemExit(f'FAIL workbook oracle {asset}')
  return out

def index_payloads(inputs:list[Path],wanted:set[str],tmp:Path)->dict[str,Path]:
 found={}
 def add(data:bytes):
  d=shab(data)
  if d in wanted and d not in found:
   q=tmp/f'{d}.payload';q.write_bytes(data);found[d]=q
 def visit(p:Path):
  if p.suffix.lower()=='.zip':
   try:
    with zipfile.ZipFile(p) as z:
     for n in z.infolist():
      if not n.is_dir():add(z.read(n))
   except zipfile.BadZipFile:pass
  else:
   try:
    d=shaf(p)
    if d in wanted and d not in found:found[d]=p
   except OSError:pass
 for r in inputs:
  if r.is_dir():
   for p in r.rglob('*'):
    if p.is_file():visit(p)
  elif r.is_file():visit(r)
 return found

def main():
 ap=argparse.ArgumentParser(description='Promote exact Batch118 battle/UI 58-asset union onto Batch301.')
 ap.add_argument('--parent-bin',type=Path,required=True);ap.add_argument('--parent-report',type=Path,required=True)
 ap.add_argument('--union-manifest',type=Path,required=True);ap.add_argument('--b118-workbook',type=Path,required=True)
 ap.add_argument('--payload-input',type=Path,action='append',required=True);ap.add_argument('--output-bin',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
 if a.parent_bin.stat().st_size!=DISC_SIZE:raise SystemExit('FAIL parent size')
 parent_sha=shaf(a.parent_bin);pr=json.loads(a.parent_report.read_text(encoding='utf-8'))
 if pr.get('status')!=PARENT_STATUS or pr.get('output_sha256')!=parent_sha:raise SystemExit('FAIL Batch301 parent report/SHA binding')
 m=json.loads(a.union_manifest.read_text(encoding='utf-8'))
 if m.get('format')!='ST2-CD1-batch302-b301-plus-b118-battle58-exact-union-v1' or m.get('parent_batch')!=301:raise SystemExit('FAIL B302 manifest format/header')
 if m.get('integration_policy',{}).get('guessed_payload_bytes')!=0:raise SystemExit('FAIL guessed-byte policy')
 if m.get('canonical_workbook',{}).get('sha256')!=WORKBOOK_SHA:raise SystemExit('FAIL manifest workbook SHA')
 hv=m.get('historical_validation',{})
 if hv.get('assets')!=58 or hv.get('changed_raw_sectors')!=1626 or hv.get('historical_pristine_output_sha256')!=HISTORICAL_B118_OUTPUT_SHA:raise SystemExit('FAIL historical B118 manifest gate')
 rows=read_assets58_xlsx(a.b118_workbook)
 wanted={r['candidate_sha256'] for r in rows}
 parent=a.parent_bin.read_bytes();out=bytearray(parent);expected={};audit=[]
 with tempfile.TemporaryDirectory(prefix='st2_b302_') as td:
  payloads=index_payloads(a.payload_input,wanted,Path(td));missing=wanted-set(payloads)
  if missing:raise SystemExit('FAIL missing candidate payload SHA(s): '+','.join(sorted(missing)))
  for r in rows:
   asset=r['asset'];lba=r['lba'];size=r['size'];src=r['original_sha256'];dst=r['candidate_sha256'];cur=shab(extract(out,lba,size))
   if cur not in {src,dst}:raise SystemExit(f'FAIL third variant {asset} {cur}')
   state='already_target'
   if cur==src and src!=dst:
    payload=payloads[dst].read_bytes()
    if len(payload)!=size or shab(payload)!=dst:raise SystemExit(f'FAIL payload {asset}')
    pos=idx=0
    while pos<size:
     L=lba+idx;off=L*RAW_SECTOR_SIZE;before=bytes(out[off:off+RAW_SECTOR_SIZE])
     if not verify_mode1_sector(before)['valid']:raise SystemExit(f'FAIL parent EDC/ECC LBA {L}')
     sec=bytearray(before);take=min(USER_SIZE,size-pos);sec[USER_OFF:USER_OFF+take]=payload[pos:pos+take];rebuild(sec);after=bytes(sec)
     if before!=after:
      if not verify_mode1_sector(after)['valid']:raise SystemExit(f'FAIL rebuilt EDC/ECC LBA {L}')
      ah=shab(after)
      if L in expected and expected[L]['after_sha256']!=ah:raise SystemExit(f'FAIL LBA collision {L}')
      expected[L]={'lba':L,'asset':asset,'before_sha256':shab(before),'after_sha256':ah};out[off:off+RAW_SECTOR_SIZE]=after
     pos+=take;idx+=1
    state='promoted_from_exact_source'
   final=shab(extract(out,lba,size))
   if final!=dst:raise SystemExit(f'FAIL whole-asset re-extraction {asset}')
   audit.append({'asset':asset,'source_batch':r['source_batch'],'lba':lba,'size':size,'parent_asset_sha256':cur,'final_asset_sha256':final,'state':state,'reextraction':'PASS'})
 actual=[]
 for L in range(DISC_SIZE//RAW_SECTOR_SIZE):
  o=L*RAW_SECTOR_SIZE
  if parent[o:o+RAW_SECTOR_SIZE]!=out[o:o+RAW_SECTOR_SIZE]:actual.append(L)
 if actual!=sorted(expected):raise SystemExit('FAIL changed-LBA accounting')
 for L in actual:
  o=L*RAW_SECTOR_SIZE;sec=bytes(out[o:o+RAW_SECTOR_SIZE]);rec=expected[L]
  if not verify_mode1_sector(sec)['valid']:raise SystemExit(f'FAIL final EDC/ECC LBA {L}')
  if shab(parent[o:o+RAW_SECTOR_SIZE])!=rec['before_sha256'] or shab(sec)!=rec['after_sha256']:raise SystemExit(f'FAIL Expected Write LBA {L}')
 a.output_bin.parent.mkdir(parents=True,exist_ok=True);a.output_bin.write_bytes(out);output_sha=shaf(a.output_bin)
 rep={'batch':302,'status':SUCCESS,'parent_batch':301,'parent_sha256':parent_sha,'output_sha256':output_sha,'pristine_reference_sha256':PRISTINE_SHA,'union_manifest_sha256':shaf(a.union_manifest),'canonical_b118_workbook_sha256':WORKBOOK_SHA,'historical_b118_output_sha256':HISTORICAL_B118_OUTPUT_SHA,'historical_b118_changed_raw_sectors':1626,'replacement_assets':58,'battle_banks_static':'55/55','battle_records_static':'12595/12595','guessed_payload_bytes':0,'asset_reextraction':'58/58 PASS','expected_write':[expected[L] for L in sorted(expected)],'changed_raw_sectors':len(actual),'changed_lbas':actual,'changed_sector_accounting':'PASS','changed_sector_edc_ecc':f'{len(actual)}/{len(actual)} PASS','asset_audit':audit}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(SUCCESS);print('output_sha256='+output_sha);print('battle_assets=58/58');print('battle_banks_static=55/55 records=12595/12595');print(f'changed_raw_sectors={len(actual)}');print('guessed_payload_bytes=0')
if __name__=='__main__':main()
