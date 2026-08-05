#!/usr/bin/env python3
"""Compose exact ST2 Disc 1 production manifests without payload inference."""
from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    for key in ('source_disc', 'scope', 'assets'):
        if key not in data: raise ValueError(f'{path}: missing {key}')
    return data


def compose(paths: list[Path]) -> dict:
    if not paths: raise ValueError('no manifests')
    docs = [load(p) for p in paths]
    disc = docs[0]['source_disc']
    assets, seen_paths, extents = [], set(), []
    groups, story, movie, subtitles = {}, 0, 0, 0
    for path, doc in zip(paths, docs):
        if doc['source_disc'] != disc: raise ValueError(f'{path}: source Disc mismatch')
        for asset in doc['assets']:
            iso = str(asset['iso_path'])
            if iso in seen_paths: raise ValueError(f'duplicate asset: {iso}')
            seen_paths.add(iso)
            size = int(asset['size']); lba = int(asset['lba'])
            if size <= 0 or lba < 0: raise ValueError(f'invalid extent: {iso}')
            for key in ('source_sha256', 'replacement_sha256'):
                value = str(asset[key]).lower()
                if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                    raise ValueError(f'invalid {key}: {iso}')
            sectors = (size + int(disc['user_size']) - 1) // int(disc['user_size'])
            extents.append((lba, lba + sectors, iso))
            assets.append(asset)
            category = asset.get('category', '')
            story += category == 'story'; movie += category == 'movie'
            subtitles += int(asset.get('subtitle_events', 0))
            group = asset.get('group', '')
            groups[group] = groups.get(group, 0) + 1
    extents.sort()
    for left, right in zip(extents, extents[1:]):
        if left[1] > right[0]: raise ValueError(f'overlap: {left[2]} / {right[2]}')
    return {
        'format': 'st2-disc1-production-assets-v1',
        'goal': 'CD1_100_PERCENT',
        'source_disc': disc,
        'scope': {
            'asset_count': len(assets),
            'story_assets': story,
            'movie_assets': movie,
            'subtitle_events': subtitles,
            'groups': groups,
            'composed_from': [str(p) for p in paths],
        },
        'assets': assets,
    }


def selftest() -> dict:
    disc = {'size': 23520, 'sha256': '0' * 64, 'raw_sector_size': 2352, 'user_offset': 16, 'user_size': 2048}
    a = {'format':'st2-disc1-production-assets-v1','goal':'CD1_100_PERCENT','source_disc':disc,'scope':{},'assets':[{'iso_path':'A.BIN','lba':1,'size':17,'source_sha256':'1'*64,'replacement_sha256':'2'*64,'category':'story','group':'A'}]}
    b = {'format':'st2-disc1-production-assets-v1','goal':'CD1_100_PERCENT','source_disc':disc,'scope':{},'assets':[{'iso_path':'B.BIN','lba':3,'size':19,'source_sha256':'3'*64,'replacement_sha256':'4'*64,'category':'movie','group':'B','subtitle_events':2}]}
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); pa=root/'a.json'; pb=root/'b.json'
        pa.write_text(json.dumps(a),encoding='utf-8'); pb.write_text(json.dumps(b),encoding='utf-8')
        out=compose([pa,pb])
    ok=out['scope']['asset_count']==2 and out['scope']['story_assets']==1 and out['scope']['movie_assets']==1 and out['scope']['subtitle_events']==2
    return {'status':'PASS' if ok else 'FAIL','asset_count':out['scope']['asset_count']}


def main() -> int:
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='cmd',required=True)
    c=sub.add_parser('compose'); c.add_argument('manifests',nargs='+',type=Path); c.add_argument('--output',required=True,type=Path)
    sub.add_parser('selftest'); args=parser.parse_args()
    if args.cmd=='selftest': result=selftest()
    else:
        result=compose(args.manifests); args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        result={'status':'PASS','output':str(args.output),'asset_count':result['scope']['asset_count'],'story_assets':result['scope']['story_assets'],'movie_assets':result['scope']['movie_assets']}
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['status']=='PASS' else 2

if __name__=='__main__': raise SystemExit(main())
