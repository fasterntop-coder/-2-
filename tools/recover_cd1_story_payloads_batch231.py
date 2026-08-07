#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, zipfile
from pathlib import Path

TARGETS = {
    "6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743": ("SK0501.BIN", 246748),
    "0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc": ("SK0502.BIN", 107920),
    "c844f857de7260e0b2746d7702460709393d8b08821986129cc5e09de103e76b": ("SK0503.BIN", 97324),
    "0a2d0edf358b8fe6ab6edbc058e7e1263fc466706312bec43fd9994eb38419d9": ("SKCM02.BIN", 129652),
    "c3e78d0b32b87d58d720c0fdd616fbc2fba232b306abe8c528d66a524664c4f8": ("SKCM04.BIN", 91196),
    "cfd966f1cc1783f0da0f988aba92bd7591237cacb10c633da0063ce1f71c29f4": ("SKCM05.BIN", 91416),
}

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(4*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default='.')
    ap.add_argument('--out', default='BATCH231_RECOVERED')
    args = ap.parse_args()
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    found, errors = {}, []

    for p in root.rglob('*'):
        if not p.is_file() or p.resolve().is_relative_to(out.resolve()):
            continue
        try:
            if p.suffix.lower() == '.zip':
                with zipfile.ZipFile(p) as z:
                    for zi in z.infolist():
                        if zi.is_dir():
                            continue
                        expected_sizes = {v[1] for v in TARGETS.values()}
                        if zi.file_size not in expected_sizes:
                            continue
                        data = z.read(zi)
                        h = sha256_bytes(data)
                        if h in TARGETS and h not in found:
                            name, size = TARGETS[h]
                            if len(data) != size: raise ValueError('size mismatch')
                            dst = out / name
                            dst.write_bytes(data)
                            found[h] = {"target":name,"sha256":h,"source":f"{p}!{zi.filename}","size":size}
            else:
                if p.stat().st_size not in {v[1] for v in TARGETS.values()}:
                    continue
                h = sha256_file(p)
                if h in TARGETS and h not in found:
                    name, size = TARGETS[h]
                    dst = out / name
                    shutil.copyfile(p, dst)
                    found[h] = {"target":name,"sha256":h,"source":str(p),"size":size}
        except Exception as e:
            errors.append({"path":str(p),"error":str(e)})

    missing = [{"target":n,"sha256":h,"size":s} for h,(n,s) in TARGETS.items() if h not in found]
    result = {"status":"PASS_ALL_RECOVERED" if not missing else "PARTIAL_OR_MISSING","found":list(found.values()),"missing":missing,"errors":errors}
    (out/'BATCH231_RECOVERY_RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 2

if __name__ == '__main__':
    raise SystemExit(main())
