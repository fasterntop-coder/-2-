#!/usr/bin/env python3
"""Recover and integrate exact ST2 Disc 1 translated production assets.

Scans loose files, ZIP members, and MODE1/2352 checkpoint BINs. Only complete
size + SHA-256 matches are accepted. Builds from the exact pristine Disc 1,
requires per-asset Expected Write hashes, rebuilds EDC/ECC, and re-extracts all
applied assets before keeping an output.
"""
from __future__ import annotations

import argparse, hashlib, io, json, shutil, tempfile, zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

CHUNK = 8 * 1024 * 1024
SYNC = bytes([0] + [0xFF] * 10 + [0])


def shab(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def shas(stream: BinaryIO) -> str:
    h = hashlib.sha256()
    while block := stream.read(CHUNK): h.update(block)
    return h.hexdigest()
def shaf(path: Path) -> str:
    with path.open('rb') as f: return shas(f)
def files(root: Path) -> Iterable[Path]: return (p for p in root.rglob('*') if p.is_file())


def tables() -> tuple[list[int], list[int], list[int]]:
    f = [0] * 256; b = [0] * 256; edc = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        f[i] = j & 0xFF; b[(i ^ j) & 0xFF] = i
        x = i
        for _ in range(8): x = (x >> 1) ^ (0xD8018001 if x & 1 else 0)
        edc[i] = x & 0xFFFFFFFF
    return f, b, edc


F_LUT, B_LUT, EDC_LUT = tables()


def edc(data: bytes) -> int:
    result = 0
    for value in data: result = EDC_LUT[(result ^ value) & 0xFF] ^ (result >> 8)
    return result & 0xFFFFFFFF


def ecc(source: bytes, major_count: int, minor_count: int,
        major_mult: int, minor_inc: int) -> bytes:
    size = major_count * minor_count
    if len(source) < size: raise ValueError('short ECC source')
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            value = source[index]
            index = (index + minor_inc) % size
            a ^= value; b ^= value; a = F_LUT[a]
        a = B_LUT[F_LUT[a] ^ b]
        out[major] = a; out[major + major_count] = a ^ b
    return bytes(out)


def rebuild_sector(sector: bytes) -> bytes:
    if len(sector) != 2352 or sector[:12] != SYNC or sector[15] != 1:
        raise ValueError('not MODE1/2352')
    out = bytearray(sector)
    out[2064:2068] = edc(bytes(out[:2064])).to_bytes(4, 'little')
    out[2068:2076] = b'\0' * 8
    out[2076:2248] = ecc(bytes(out[12:2076]), 86, 24, 2, 86)
    out[2248:2352] = ecc(bytes(out[12:2248]), 52, 43, 86, 88)
    return bytes(out)


def valid_sector(sector: bytes) -> bool:
    try: return rebuild_sector(sector) == sector
    except ValueError: return False


def bcd(value: int) -> int: return ((value // 10) << 4) | value % 10

def make_sector(lba: int, user: bytes) -> bytes:
    if len(user) != 2048: raise ValueError('user size')
    address = lba + 150; out = bytearray(2352); out[:12] = SYNC
    out[12] = bcd(address // 4500); out[13] = bcd((address // 75) % 60)
    out[14] = bcd(address % 75); out[15] = 1; out[16:2064] = user
    return rebuild_sector(bytes(out))


def extract(stream: BinaryIO, asset: dict, disc: dict) -> bytes:
    raw = int(disc['raw_sector_size']); off = int(disc['user_offset']); user = int(disc['user_size'])
    remaining = int(asset['size']); lba = int(asset['lba']); out = bytearray()
    while remaining:
        stream.seek(lba * raw); sector = stream.read(raw)
        if len(sector) != raw: raise ValueError(f'short LBA {lba}')
        if raw == 2352 and (sector[:12] != SYNC or sector[15] != 1): raise ValueError(f'bad MODE1 LBA {lba}')
        take = min(user, remaining); out += sector[off:off + take]
        remaining -= take; lba += 1
    return bytes(out)


def validate_manifest(m: dict) -> None:
    disc = m['source_disc']; assets = m['assets']
    if not assets: raise ValueError('empty assets')
    paths = set(); extents = []
    for a in assets:
        path = str(a['iso_path'])
        if path in paths: raise ValueError(f'duplicate {path}')
        paths.add(path)
        for key in ('source_sha256', 'replacement_sha256'):
            value = str(a[key]).lower()
            if len(value) != 64 or any(c not in '0123456789abcdef' for c in value): raise ValueError(f'bad {key}: {path}')
        sectors = (int(a['size']) + int(disc['user_size']) - 1) // int(disc['user_size'])
        extents.append((int(a['lba']), int(a['lba']) + sectors, path))
    extents.sort()
    for left, right in zip(extents, extents[1:]):
        if left[1] > right[0]: raise ValueError(f'overlap {left[2]} / {right[2]}')


def accept(data: bytes, asset: dict, out: Path, source: str, found: dict) -> bool:
    if len(data) != int(asset['size']) or shab(data) != asset['replacement_sha256']: return False
    target = out / Path(asset['iso_path']); target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != data: raise RuntimeError(f'conflict {asset["iso_path"]}')
    target.write_bytes(data)
    found[asset['iso_path']] = {'path': str(target), 'source': source, 'sha256': asset['replacement_sha256']}
    return True


def scan_checkpoint(stream: BinaryIO, label: str, m: dict, out: Path, found: dict) -> None:
    for asset in m['assets']:
        if asset['iso_path'] in found: continue
        accept(extract(stream, asset, m['source_disc']), asset, out, f'{label}@LBA{asset["lba"]}', found)


def recover(m: dict, root: Path, out: Path) -> dict:
    by_size = {}
    for a in m['assets']: by_size.setdefault(int(a['size']), []).append(a)
    disc_size = int(m['source_disc']['size']); found = {}
    for path in files(root):
        try:
            if path.suffix.lower() == '.zip':
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if info.is_dir(): continue
                        if info.file_size in by_size:
                            data = z.read(info)
                            for a in by_size[info.file_size]: accept(data, a, out, f'{path}!{info.filename}', found)
                        elif info.file_size == disc_size:
                            with z.open(info) as member:
                                if member.seekable(): scan_checkpoint(member, f'{path}!{info.filename}', m, out, found)
                                else:
                                    with tempfile.TemporaryFile() as temp:
                                        shutil.copyfileobj(member, temp, CHUNK); temp.seek(0)
                                        scan_checkpoint(temp, f'{path}!{info.filename}', m, out, found)
            else:
                size = path.stat().st_size
                if size in by_size:
                    data = path.read_bytes()
                    for a in by_size[size]: accept(data, a, out, str(path), found)
                elif size == disc_size:
                    with path.open('rb') as f: scan_checkpoint(f, str(path), m, out, found)
        except (OSError, ValueError, zipfile.BadZipFile): pass
    return found


def source_disc(m: dict, root: Path, temp: Path) -> Path | None:
    disc = m['source_disc']; size = int(disc['size']); digest = disc['sha256']
    for path in files(root):
        try:
            if path.suffix.lower() == '.zip':
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if info.is_dir() or info.file_size != size: continue
                        with z.open(info) as member:
                            if shas(member) != digest: continue
                        target = temp / Path(info.filename).name
                        with z.open(info) as src, target.open('wb') as dst: shutil.copyfileobj(src, dst, CHUNK)
                        return target
            elif path.stat().st_size == size and shaf(path) == digest: return path
        except (OSError, zipfile.BadZipFile): pass
    return None


def write_asset(src: BinaryIO, dst: BinaryIO, asset: dict, replacement: bytes, disc: dict) -> set[int]:
    raw = int(disc['raw_sector_size']); off = int(disc['user_offset']); user = int(disc['user_size'])
    cursor = 0; remaining = len(replacement); lba = int(asset['lba']); touched = set()
    while remaining:
        src.seek(lba * raw); original = src.read(raw); take = min(user, remaining)
        patched = bytearray(original); patched[off:off + take] = replacement[cursor:cursor + take]
        final = rebuild_sector(bytes(patched)) if raw == 2352 else bytes(patched)
        if final != original: dst.seek(lba * raw); dst.write(final); touched.add(lba)
        cursor += take; remaining -= take; lba += 1
    return touched


def sparse_patch(source: Path, output: Path, lbas: list[int], raw: int, result: dict, target: Path) -> str:
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr('PATCH_RESULT.json', json.dumps(result, ensure_ascii=False, indent=2))
        with source.open('rb') as a, output.open('rb') as b:
            for lba in lbas:
                a.seek(lba * raw); before = a.read(raw); b.seek(lba * raw); after = b.read(raw)
                z.writestr(f'PATCH_SECTORS/LBA_{lba}.json', json.dumps({'lba': lba, 'original_sha256': shab(before), 'patched_sha256': shab(after)}, indent=2))
                z.writestr(f'PATCH_SECTORS/LBA_{lba}.bin', after)
    return shaf(target)


def build(m: dict, source: Path, found: dict, out: Path, require_all: bool) -> dict:
    disc = m['source_disc']; missing = [a['iso_path'] for a in m['assets'] if a['iso_path'] not in found]
    if require_all and missing: return {'status': 'BLOCKED_REQUIRE_ALL_ASSETS', 'missing': missing, 'recovered_count': len(found), 'target_count': len(m['assets'])}
    applied = [a for a in m['assets'] if a['iso_path'] in found]
    if not applied: return {'status': 'BLOCKED_NO_EXACT_REPLACEMENT_ASSETS', 'missing': missing, 'recovered_count': 0, 'target_count': len(m['assets'])}
    if source.stat().st_size != int(disc['size']) or shaf(source) != disc['sha256']: raise RuntimeError('source Disc gate failed')
    raw = int(disc['raw_sector_size']); temp = out / '_BUILDING.bin'; final = out / 'Sakura_Taisen_2_Disc1_PRODUCTION_KO.bin'
    shutil.copyfile(source, temp); changed = set(); asset_report = {}
    try:
        with source.open('rb') as src, temp.open('r+b') as dst:
            for asset in applied:
                if shab(extract(src, asset, disc)) != asset['source_sha256']: raise RuntimeError(f'Expected Write failed: {asset["iso_path"]}')
                replacement = Path(found[asset['iso_path']]['path']).read_bytes()
                if len(replacement) != asset['size'] or shab(replacement) != asset['replacement_sha256']: raise RuntimeError(f'replacement gate failed: {asset["iso_path"]}')
                touched = write_asset(src, dst, asset, replacement, disc); changed |= touched
                asset_report[asset['iso_path']] = {'replacement_sha256': asset['replacement_sha256'], 'changed_sectors': len(touched), 'category': asset.get('category', ''), 'group': asset.get('group', '')}
        with temp.open('rb') as built:
            for asset in applied:
                if shab(extract(built, asset, disc)) != asset['replacement_sha256']: raise RuntimeError(f're-extraction failed: {asset["iso_path"]}')
        actual = []
        with source.open('rb') as a, temp.open('rb') as b:
            for lba in range(int(disc['size']) // raw):
                before = a.read(raw); after = b.read(raw)
                if before != after:
                    actual.append(lba)
                    if lba not in changed: raise RuntimeError(f'undeclared changed sector {lba}')
                    if raw == 2352 and not valid_sector(after): raise RuntimeError(f'EDC/ECC failed {lba}')
        if set(actual) != changed: raise RuntimeError('changed-sector accounting mismatch')
        temp.replace(final)
        cue = out / 'Sakura_Taisen_2_Disc1_PRODUCTION_KO.cue'
        cue.write_text('FILE "Sakura_Taisen_2_Disc1_PRODUCTION_KO.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n  TRACK 02 AUDIO\n    PREGAP 00:02:00\n    INDEX 01 61:56:22\n', encoding='ascii', newline='\r\n')
        groups = {}; categories = {}; subtitle_events = 0
        for a in applied:
            groups[a.get('group', '')] = groups.get(a.get('group', ''), 0) + 1
            categories[a.get('category', '')] = categories.get(a.get('category', ''), 0) + 1
            subtitle_events += int(a.get('subtitle_events', 0))
        result = {'status': 'PASS_FULL_PRODUCTION_SCOPE_BUILT' if not missing else 'PASS_PARTIAL_PRODUCTION_SCOPE_BUILT', 'source_sha256': disc['sha256'], 'output_bin': str(final), 'output_sha256': shaf(final), 'output_cue': str(cue), 'output_cue_sha256': shaf(cue), 'target_count': len(m['assets']), 'recovered_count': len(found), 'applied_count': len(applied), 'missing': missing, 'groups': groups, 'categories': categories, 'subtitle_events': subtitle_events, 'changed_sector_count': len(changed), 'changed_lbas': sorted(changed), 'assets': asset_report, 'edc_ecc': 'PASS_CHANGED_SECTORS', 're_extraction': f'PASS_{len(applied)}_OF_{len(applied)}'}
        patch = out / 'ST2_DISC1_PRODUCTION_SPARSE_PATCH.zip'; result['patch_zip_sha256'] = sparse_patch(source, final, sorted(changed), raw, result, patch); result['patch_zip'] = str(patch)
        return result
    except Exception:
        temp.unlink(missing_ok=True); final.unlink(missing_ok=True); raise


def run(manifest_path: Path, root: Path, out: Path, require_all: bool) -> dict:
    m = json.loads(manifest_path.read_text(encoding='utf-8')); validate_manifest(m); out.mkdir(parents=True, exist_ok=True)
    recovered_dir = out / 'RECOVERED_ASSETS'; recovered_dir.mkdir(exist_ok=True); found = recover(m, root, recovered_dir)
    temp = out / '_TEMP'; temp.mkdir(exist_ok=True); src = source_disc(m, root, temp)
    if src is None: result = {'status': 'PARTIAL_EXACT_ASSETS_RECOVERED_SOURCE_DISC_PENDING', 'target_count': len(m['assets']), 'recovered_count': len(found), 'missing': [a['iso_path'] for a in m['assets'] if a['iso_path'] not in found]}
    else: result = build(m, src, found, out, require_all)
    result['recovered'] = found; (out / 'PRODUCTION_RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'); return result


def selftest() -> dict:
    sectors = [make_sector(lba, bytes(((lba * 19 + i * 7 + 3) & 255) for i in range(2048))) for lba in range(16)]
    source = b''.join(sectors); disc = {'size': len(source), 'sha256': shab(source), 'raw_sector_size': 2352, 'user_offset': 16, 'user_size': 2048}
    assets = []; replacements = {}
    for name, lba, size, category in [('SAKURA2/A.MES', 2, 3000, 'story'), ('SAKURA1/B.CAK', 6, 5000, 'movie')]:
        asset = {'iso_path': name, 'lba': lba, 'size': size}; original = extract(io.BytesIO(source), asset, disc); replacement = bytes(v ^ 0x5A for v in original)
        asset.update({'source_sha256': shab(original), 'replacement_sha256': shab(replacement), 'category': category, 'group': 'synthetic', 'subtitle_events': 3 if category == 'movie' else 0}); assets.append(asset); replacements[name] = replacement
    manifest = {'format': 'synthetic', 'source_disc': disc, 'assets': assets}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); (root / 'source.bin').write_bytes(source); (root / 'SAKURA2').mkdir(); (root / 'SAKURA2/A.MES').write_bytes(replacements['SAKURA2/A.MES'])
        checkpoint = bytearray(source); asset = assets[1]; repl = replacements[asset['iso_path']]; cursor = 0; remaining = len(repl); lba = asset['lba']
        while remaining:
            pos = lba * 2352; sector = bytearray(checkpoint[pos:pos + 2352]); take = min(2048, remaining); sector[16:16 + take] = repl[cursor:cursor + take]; checkpoint[pos:pos + 2352] = rebuild_sector(bytes(sector)); cursor += take; remaining -= take; lba += 1
        with zipfile.ZipFile(root / 'checkpoint.zip', 'w') as z: z.writestr('checkpoint.bin', checkpoint)
        mp = root / 'manifest.json'; mp.write_text(json.dumps(manifest), encoding='utf-8'); result = run(mp, root, root / 'out', True); output = root / 'out/Sakura_Taisen_2_Disc1_PRODUCTION_KO.bin'
        ok = result['status'] == 'PASS_FULL_PRODUCTION_SCOPE_BUILT' and result['applied_count'] == 2 and result['subtitle_events'] == 3 and output.exists()
        if ok:
            with output.open('rb') as f:
                for a in assets: ok = ok and shab(extract(f, a, disc)) == a['replacement_sha256']
            raw = output.read_bytes(); ok = ok and all(valid_sector(raw[l * 2352:(l + 1) * 2352]) for l in result['changed_lbas'])
    return {'status': 'PASS' if ok else 'FAIL', 'roundtrip': ok}


def main() -> int:
    p = argparse.ArgumentParser(); s = p.add_subparsers(dest='cmd', required=True)
    r = s.add_parser('run'); r.add_argument('manifest', type=Path); r.add_argument('search_root', type=Path); r.add_argument('--output-dir', type=Path, default=Path('output/CD1_PRODUCTION')); r.add_argument('--require-all', action='store_true')
    v = s.add_parser('validate'); v.add_argument('manifest', type=Path); s.add_parser('selftest'); a = p.parse_args()
    if a.cmd == 'selftest': result = selftest()
    elif a.cmd == 'validate':
        m = json.loads(a.manifest.read_text(encoding='utf-8')); validate_manifest(m); result = {'status': 'PASS', 'asset_count': len(m['assets']), 'groups': sorted({x.get('group', '') for x in m['assets']})}
    else: result = run(a.manifest, a.search_root, a.output_dir, a.require_all)
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if str(result['status']).startswith('PASS') else 2


if __name__ == '__main__': raise SystemExit(main())
