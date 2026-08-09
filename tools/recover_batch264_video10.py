#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path

MANIFEST=Path('manifests/CD1_BATCH264_VIDEO10_RECOVERY.json')

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        while c:=f.read(8*1024*1024): h.update(c)
    return h.hexdigest()

def sha256_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def main()->int:
    ap=argparse.ArgumentParser(description='Recover and seal exact Batch264 VIDEO10 payloads without guessed bytes')
    ap.add_argument('--roots',type=Path,nargs='+',required=True)
    ap.add_argument('--output-dir',type=Path,default=Path('BATCH264_VIDEO10_RECOVERED'))
    ap.add_argument('--sealed-manifest',type=Path,default=Path('manifests/CD1_BATCH264_VIDEO10_SEALED.json'))
    a=ap.parse_args(); m=json.loads(MANIFEST.read_text(encoding='utf-8')); assets=m['assets']; a.output_dir.mkdir(parents=True,exist_ok=True)
    by_name={Path(x['iso_path']).name:x for x in assets}; recovered={}; evidence=[]
    def accept(name:str,data:bytes,source:str,mode:str):
        if name not in by_name or name in recovered:return
        x=by_name[name]
        if len(data)!=x['size']:return
        h=sha256_bytes(data)
        if x['recovery_mode']=='EXACT_SHA256' and h!=x['replacement_sha256']:return
        if h==x['source_sha256']:return
        out=a.output_dir/name;out.write_bytes(data);recovered[name]=h;evidence.append({'asset':name,'source':source,'recovery_mode':mode,'replacement_sha256':h})
    for root in a.roots:
        if not root.exists():continue
        paths=[root] if root.is_file() else list(root.rglob('*'))
        for p in paths:
            if not p.is_file():continue
            n=p.name
            if n in by_name:
                try:accept(n,p.read_bytes(),str(p),'LOOSE_EXACT')
                except OSError:pass
            if p.suffix.lower()=='.zip':
                zsha=sha256_file(p)
                trust_targets=[x for x in assets if x['recovery_mode']=='TRUST_PACKAGE' and x['trust_package_sha256']==zsha]
                try:
                    with zipfile.ZipFile(p) as z:
                        for zi in z.infolist():
                            bn=Path(zi.filename).name
                            if bn in by_name:
                                data=z.read(zi)
                                if any(Path(x['iso_path']).name==bn for x in trust_targets):accept(bn,data,f'{p}!{zi.filename}','TRUST_PACKAGE_EXACT')
                                else:accept(bn,data,f'{p}!{zi.filename}','ZIP_EXACT')
                except (zipfile.BadZipFile,OSError,RuntimeError):pass
    sealed=[]
    for x in assets:
        n=Path(x['iso_path']).name
        y=dict(x);y['recovered']=n in recovered
        if n in recovered:y['sealed_replacement_sha256']=recovered[n]
        sealed.append(y)
    out={'format':'ST2-CD1-BATCH264-VIDEO10-SEALED-v1','batch':264,'source_manifest':str(MANIFEST),'asset_count':10,'recovered_count':len(recovered),'missing':[Path(x['iso_path']).name for x in assets if Path(x['iso_path']).name not in recovered],'assets':sealed,'evidence':evidence,'policy':{'guessed_payload_bytes':False,'all_promotion_hashes_must_be_sealed':True},'status':'PASS_VIDEO10_10_OF_10_SEALED' if len(recovered)==10 else 'PARTIAL_EXACT_RECOVERY_NO_PROMOTION'}
    a.sealed_manifest.parent.mkdir(parents=True,exist_ok=True);a.sealed_manifest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':out['status'],'recovered':len(recovered),'missing':out['missing']},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
