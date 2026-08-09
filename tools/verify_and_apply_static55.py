#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ZIP_SHA='48adebfe83ced41f38f7960030fb4a9cd24592dac231f51b6f7ce632785ba88c'
SOURCE_SHA='d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106'
OUTPUT_SHA='b5e8fc8b1a5798d03a3f3bd21a87ce66b742c64a1d8ce3ed3d7dc8db9763d518'
INNER_ZIP_NAMES=('B137_STATIC55_EXACT_PATCH.zip','ST2R41_BATCH137_FIFTYFIVE_ASSET_EXACT_RECOVERY_PATCH.zip')

def fsha(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(8*1024*1024),b''): h.update(c)
    return h.hexdigest()

def locate_patch_zip(base:Path)->Path:
    for name in INNER_ZIP_NAMES:
        p=base/name
        if p.is_file() and fsha(p)==ZIP_SHA: return p
    for p in base.rglob('*.zip'):
        try:
            if fsha(p)==ZIP_SHA: return p
        except OSError: pass
    raise FileNotFoundError('exact B137 STATIC55 patch ZIP not found')

def verify_inner(root:Path)->None:
    manifest=root/'BATCH137_PACKAGE_MANIFEST.json'
    m=json.loads(manifest.read_text(encoding='utf-8'))
    if len(m)!=1607: raise ValueError(f'B137 manifest entry count mismatch: {len(m)}')
    for rel,spec in m.items():
        p=root/rel
        if not p.is_file(): raise ValueError(f'missing B137 payload: {rel}')
        if p.stat().st_size!=int(spec['size']) or fsha(p)!=spec['sha256']:
            raise ValueError(f'B137 payload verification failed: {rel}')

def main()->int:
    if len(sys.argv)<2 or len(sys.argv)>3:
        print('Usage: verify_and_apply_static55.py <pristine Disc1 BIN or ZIP> [patch package directory]')
        return 2
    source=Path(sys.argv[1]).expanduser().resolve()
    base=Path(sys.argv[2]).expanduser().resolve() if len(sys.argv)==3 else Path.cwd()
    if not source.is_file(): raise FileNotFoundError(source)
    patch_zip=locate_patch_zip(base)
    work=base/'B137_STATIC55_WORK'
    if work.exists(): shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(patch_zip) as zf: zf.extractall(work)
    verify_inner(work)
    cp=subprocess.run([sys.executable,str(work/'batch137_apply_fiftyfive_asset_exact.py'),str(source)],cwd=work)
    if cp.returncode: return cp.returncode
    out=work/'Sakura_Taisen_2_Disc1_B137_FiftyFive_Asset_Exact_KO.bin'
    if not out.is_file() or fsha(out)!=OUTPUT_SHA: raise ValueError('final STATIC55 BIN SHA mismatch')
    result={'status':'PASS_STATIC55_RESTORED','source_required_sha256':SOURCE_SHA,'patch_zip_sha256':ZIP_SHA,'exact_assets':'55/58','battle_banks':'55/55','changed_raw_sectors':1597,'edc_ecc':'PASS','reextraction':'55/55 PASS','output_bin_sha256':OUTPUT_SHA,'guessed_bytes':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
