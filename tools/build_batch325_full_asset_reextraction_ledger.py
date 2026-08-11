#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

RAW_SECTOR_SIZE = 2352
USER_DATA_OFFSET = 16
USER_DATA_SIZE = 2048
DISC_SIZE = 659_293_824
TRACK01_SECTORS = 278_722
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_EXTRACTED_FILES = 1626
PASS = "PASS_B325_FULL_ASSET_REEXTRACTION_LEDGER"


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class RawIso:
    def __init__(self, path: Path):
        self.path = path
        self.f = path.open("rb")

    def close(self) -> None:
        self.f.close()

    def block(self, lba: int) -> bytes:
        if not (0 <= lba < TRACK01_SECTORS):
            die(f"logical block out of Track01 range: {lba}")
        self.f.seek(lba * RAW_SECTOR_SIZE + USER_DATA_OFFSET)
        b = self.f.read(USER_DATA_SIZE)
        if len(b) != USER_DATA_SIZE:
            die(f"short user-data read at LBA {lba}")
        return b

    def extent(self, lba: int, size: int) -> bytes:
        if size < 0:
            die("negative extent size")
        out = bytearray()
        blocks = (size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        for i in range(blocks):
            out += self.block(lba + i)
        return bytes(out[:size])


@dataclass(frozen=True)
class Entry:
    path: str
    lba: int
    size: int
    flags: int
    is_dir: bool


def both_endian_u32(b: bytes, off: int, field: str) -> int:
    if off + 8 > len(b):
        die(f"truncated both-endian field {field}")
    le = int.from_bytes(b[off:off+4], "little")
    be = int.from_bytes(b[off+4:off+8], "big")
    if le != be:
        die(f"ISO both-endian mismatch {field}: le={le} be={be}")
    return le


def parse_record(rec: bytes, parent: str) -> Entry | None:
    if len(rec) < 34:
        die("directory record shorter than 34 bytes")
    lba = both_endian_u32(rec, 2, "extent")
    size = both_endian_u32(rec, 10, "size")
    flags = rec[25]
    name_len = rec[32]
    if 33 + name_len > len(rec):
        die("directory record name overruns record")
    raw_name = rec[33:33+name_len]
    if raw_name in (b"\x00", b"\x01"):
        return None
    try:
        name = raw_name.decode("ascii")
    except UnicodeDecodeError as exc:
        die(f"non-ASCII ISO9660 identifier under {parent}: {exc}")
    if ";" in name:
        base, version = name.rsplit(";", 1)
        if not version.isdigit():
            die(f"non-numeric ISO version in {name}")
        name = base
    if not name:
        die("empty normalized ISO filename")
    path = f"{parent}/{name}" if parent else name
    return Entry(path=path, lba=lba, size=size, flags=flags, is_dir=bool(flags & 0x02))


def iter_directory_records(iso: RawIso, lba: int, size: int, parent: str) -> list[Entry]:
    data = iso.extent(lba, size)
    entries: list[Entry] = []
    pos = 0
    while pos < len(data):
        rec_len = data[pos]
        if rec_len == 0:
            pos = ((pos // USER_DATA_SIZE) + 1) * USER_DATA_SIZE
            continue
        if pos + rec_len > len(data):
            die(f"directory record overruns directory {parent or '/'}")
        rec = data[pos:pos+rec_len]
        ent = parse_record(rec, parent)
        if ent is not None:
            entries.append(ent)
        pos += rec_len
    return entries


def scan_iso(iso: RawIso) -> tuple[list[Entry], dict[str, object]]:
    pvd = iso.block(16)
    if pvd[0] != 1 or pvd[1:6] != b"CD001" or pvd[6] != 1:
        die("Primary Volume Descriptor missing at logical block 16")
    logical_block_size = int.from_bytes(pvd[128:130], "little")
    logical_block_size_be = int.from_bytes(pvd[130:132], "big")
    if logical_block_size != USER_DATA_SIZE or logical_block_size_be != USER_DATA_SIZE:
        die(f"unsupported ISO logical block size {logical_block_size}/{logical_block_size_be}")
    root_len = pvd[156]
    if root_len < 34:
        die("invalid PVD root directory record")
    root = pvd[156:156+root_len]
    root_lba = both_endian_u32(root, 2, "root extent")
    root_size = both_endian_u32(root, 10, "root size")

    files: list[Entry] = []
    seen_dirs: set[tuple[int, int]] = set()
    stack: list[tuple[str, int, int]] = [("", root_lba, root_size)]
    all_paths: set[str] = set()
    dir_count = 0

    while stack:
        parent, lba, size = stack.pop()
        key = (lba, size)
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        dir_count += 1
        for ent in iter_directory_records(iso, lba, size, parent):
            if ent.path in all_paths:
                die(f"duplicate normalized ISO path {ent.path}")
            all_paths.add(ent.path)
            if ent.flags & 0x80:
                die(f"multi-extent ISO entry unsupported by exact gate: {ent.path}")
            if ent.lba < 0 or ent.lba >= TRACK01_SECTORS:
                die(f"entry extent starts outside Track01: {ent.path} LBA={ent.lba}")
            blocks = (ent.size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
            if ent.lba + blocks > TRACK01_SECTORS:
                die(f"entry extent exceeds Track01: {ent.path}")
            if ent.is_dir:
                stack.append((ent.path, ent.lba, ent.size))
            else:
                files.append(ent)

    files.sort(key=lambda e: e.path)
    meta = {
        "pvd_lba": 16,
        "root_lba": root_lba,
        "root_size": root_size,
        "directory_count": dir_count,
        "file_count": len(files),
    }
    return files, meta


def content_sha(iso: RawIso, ent: Entry) -> str:
    return hashlib.sha256(iso.extent(ent.lba, ent.size)).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=(
        "Batch325: re-scan the entire Disc1 ISO9660 namespace from pristine and candidate RAW BINs, "
        "re-extract every regular file, hash every file, prove filesystem geometry/path identity, and "
        "materialize a canonical changed/unchanged asset ledger. No guessed bytes are permitted."
    ))
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    for p in (args.pristine_bin, args.candidate_bin):
        if not p.is_file():
            die(f"missing input {p}")
        if p.stat().st_size != DISC_SIZE:
            die(f"Disc size mismatch for {p}: {p.stat().st_size}")
    if args.ledger.exists() or args.report.exists():
        die("refusing to overwrite output")

    pristine_sha = sha256_file(args.pristine_bin)
    candidate_sha = sha256_file(args.candidate_bin)
    if pristine_sha != PRISTINE_SHA256:
        die(f"pristine SHA mismatch {pristine_sha}")
    if candidate_sha != CANDIDATE_SHA256:
        die(f"candidate SHA mismatch {candidate_sha}")

    p_iso = RawIso(args.pristine_bin)
    c_iso = RawIso(args.candidate_bin)
    try:
        p_files, p_meta = scan_iso(p_iso)
        c_files, c_meta = scan_iso(c_iso)
        if p_meta != c_meta:
            die(f"filesystem top-level metadata drift: pristine={p_meta} candidate={c_meta}")
        if len(p_files) != EXPECTED_EXTRACTED_FILES:
            die(f"unexpected Disc1 extracted file count {len(p_files)} != {EXPECTED_EXTRACTED_FILES}")
        if len(c_files) != EXPECTED_EXTRACTED_FILES:
            die(f"candidate extracted file count {len(c_files)} != {EXPECTED_EXTRACTED_FILES}")

        p_map = {e.path: e for e in p_files}
        c_map = {e.path: e for e in c_files}
        if p_map.keys() != c_map.keys():
            missing = sorted(p_map.keys() - c_map.keys())[:20]
            added = sorted(c_map.keys() - p_map.keys())[:20]
            die(f"filesystem path-set drift missing={missing} added={added}")

        rows: list[dict[str, object]] = []
        changed = 0
        unchanged = 0
        ledger_chain = hashlib.sha256()
        changed_chain = hashlib.sha256()

        for ordinal, path in enumerate(sorted(p_map)):
            pe = p_map[path]
            ce = c_map[path]
            if (pe.lba, pe.size, pe.flags, pe.is_dir) != (ce.lba, ce.size, ce.flags, ce.is_dir):
                die(f"filesystem geometry drift at {path}: pristine={pe} candidate={ce}")
            p_hash = content_sha(p_iso, pe)
            c_hash = content_sha(c_iso, ce)
            is_changed = p_hash != c_hash
            changed += int(is_changed)
            unchanged += int(not is_changed)
            row = {
                "ordinal": ordinal,
                "path": path,
                "lba": pe.lba,
                "size": pe.size,
                "flags": pe.flags,
                "pristine_sha256": p_hash,
                "candidate_sha256": c_hash,
                "changed": is_changed,
            }
            canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ledger_chain.update(canonical + b"\n")
            if is_changed:
                changed_chain.update(canonical + b"\n")
            rows.append(row)
    finally:
        p_iso.close()
        c_iso.close()

    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    with args.ledger.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    ledger_sha = sha256_file(args.ledger)
    report = {
        "batch": 325,
        "status": PASS,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "estimated_or_guessed_bytes": 0,
            "prior_full_track_gate": 324,
        },
        "filesystem": p_meta,
        "reextraction": {
            "regular_files_reextracted_pristine": len(rows),
            "regular_files_reextracted_candidate": len(rows),
            "path_set_identical": True,
            "extent_size_flags_identical": True,
            "changed_files": changed,
            "unchanged_files": unchanged,
            "accounted_files": changed + unchanged,
            "expected_files": EXPECTED_EXTRACTED_FILES,
        },
        "ledger": {
            "path": args.ledger.name,
            "sha256": ledger_sha,
            "canonical_row_chain_sha256": ledger_chain.hexdigest(),
            "changed_row_chain_sha256": changed_chain.hexdigest(),
            "rows": len(rows),
        },
        "gates": {
            "full_bin_sha256_pristine": "PASS",
            "full_bin_sha256_candidate": "PASS",
            "iso9660_pvd": "PASS",
            "full_namespace_rescan": "PASS",
            "full_asset_reextraction": f"{len(rows)}/{EXPECTED_EXTRACTED_FILES} PASS",
            "filesystem_geometry_identity": f"{len(rows)}/{EXPECTED_EXTRACTED_FILES} PASS",
            "asset_accounting": f"{changed}+{unchanged}={len(rows)} PASS",
            "estimated_or_guessed_bytes": 0,
        },
        "hardware_validation": "PENDING; exact filesystem/file-content gate only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(PASS)
    print(f"reextracted={len(rows)}/{EXPECTED_EXTRACTED_FILES} PASS")
    print(f"changed_files={changed} unchanged_files={unchanged}")
    print(f"ledger_sha256={ledger_sha}")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
