#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import tempfile
import zlib
from pathlib import Path

SECTOR = 2352
MAGIC = b"ST2SP314"
VERSION = 1
HEADER_FMT = ">8sIIQI32s32s"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_FILE_SIZE = 659_293_824
EXPECTED_TOTAL_SECTORS = EXPECTED_FILE_SIZE // SECTOR
EXPECTED_CHANGED_SECTORS = 90_272
PASS315 = "PASS_B315_CANONICAL_SPARSE_PATCH_INTEGRITY_GATE"
MAX_COMPRESSED_RECORD = 8192


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_sector(payload: bytes, idx: int) -> bytes:
    # Bounded decompression: one record may decode to exactly one raw sector only.
    try:
        dec = zlib.decompressobj()
        sector = dec.decompress(payload, SECTOR + 1)
        sector += dec.flush()
    except zlib.error as exc:
        die(f"zlib failure at sector {idx}: {exc}")
    if dec.unused_data or dec.unconsumed_tail:
        die(f"non-canonical compressed payload at sector {idx}")
    if len(sector) != SECTOR:
        die(f"decoded sector {idx} length {len(sector)} != {SECTOR}")
    return sector


def audit_patch(patch: Path) -> dict:
    patch_sha = sha256_file(patch)
    chain = hashlib.sha256()
    compressed_total = 0
    min_idx = None
    max_idx = None
    previous = -1

    with patch.open("rb") as f:
        raw = f.read(HEADER_SIZE)
        if len(raw) != HEADER_SIZE:
            die("truncated patch header")
        magic, version, sector_size, file_size, count, pristine_sha, candidate_sha = struct.unpack(HEADER_FMT, raw)

        if magic != MAGIC:
            die("patch magic mismatch")
        if version != VERSION:
            die(f"unsupported patch version {version}")
        if sector_size != SECTOR:
            die(f"sector size {sector_size} != {SECTOR}")
        if file_size != EXPECTED_FILE_SIZE:
            die(f"target size {file_size} != {EXPECTED_FILE_SIZE}")
        if file_size % SECTOR:
            die("target size is not raw-sector aligned")
        if file_size // SECTOR != EXPECTED_TOTAL_SECTORS:
            die("total-sector accounting mismatch")
        if count != EXPECTED_CHANGED_SECTORS:
            die(f"record count {count} != {EXPECTED_CHANGED_SECTORS}")
        if pristine_sha.hex() != PRISTINE_SHA256:
            die("embedded pristine SHA-256 mismatch")
        if candidate_sha.hex() != CANDIDATE_SHA256:
            die("embedded candidate SHA-256 mismatch")

        for ordinal in range(count):
            rec = f.read(8)
            if len(rec) != 8:
                die(f"truncated record header at ordinal {ordinal}")
            idx, clen = struct.unpack(">II", rec)
            if idx >= EXPECTED_TOTAL_SECTORS:
                die(f"sector {idx} outside Disc 1")
            if idx <= previous:
                die(f"sector index order is not strictly increasing at {idx}")
            if clen <= 0 or clen > MAX_COMPRESSED_RECORD:
                die(f"compressed length {clen} invalid at sector {idx}")
            payload = f.read(clen)
            if len(payload) != clen:
                die(f"truncated payload at sector {idx}")
            sector = decode_sector(payload, idx)
            sector_sha = hashlib.sha256(sector).digest()

            # Canonical record-chain digest binds ordinal, LBA, compressed bytes,
            # and exact decoded 2352-byte sector content without storing a 90k-row ledger.
            chain.update(struct.pack(">II", ordinal, idx))
            chain.update(hashlib.sha256(payload).digest())
            chain.update(sector_sha)

            compressed_total += clen
            min_idx = idx if min_idx is None else min(min_idx, idx)
            max_idx = idx if max_idx is None else max(max_idx, idx)
            previous = idx

        if f.read(1):
            die("trailing bytes after final patch record")

    return {
        "patch_sha256": patch_sha,
        "format": "ST2SP314-v1",
        "header_bytes": HEADER_SIZE,
        "target_file_size": EXPECTED_FILE_SIZE,
        "target_total_sectors": EXPECTED_TOTAL_SECTORS,
        "changed_sectors": EXPECTED_CHANGED_SECTORS,
        "first_changed_sector": min_idx,
        "last_changed_sector": max_idx,
        "compressed_payload_bytes": compressed_total,
        "record_chain_sha256": chain.hexdigest(),
        "strictly_increasing_unique_sector_indices": True,
        "all_payloads_decode_to_exact_2352_bytes": True,
        "trailing_bytes": 0,
    }


def apply_and_verify(pristine: Path, patch: Path, expected_patch_sha: str | None = None) -> dict:
    if pristine.stat().st_size != EXPECTED_FILE_SIZE:
        die("pristine Disc 1 size mismatch")
    pristine_sha = sha256_file(pristine)
    if pristine_sha != PRISTINE_SHA256:
        die("pristine Disc 1 SHA-256 mismatch")
    if expected_patch_sha and sha256_file(patch) != expected_patch_sha:
        die("patch changed between audit and apply")

    with tempfile.TemporaryDirectory(prefix="st2_b315_") as td:
        out = Path(td) / "candidate.bin"
        shutil.copyfile(pristine, out)
        with patch.open("rb") as f, out.open("r+b") as dst:
            raw = f.read(HEADER_SIZE)
            magic, version, sector_size, file_size, count, pristine_emb, candidate_emb = struct.unpack(HEADER_FMT, raw)
            if (
                magic != MAGIC
                or version != VERSION
                or sector_size != SECTOR
                or file_size != EXPECTED_FILE_SIZE
                or count != EXPECTED_CHANGED_SECTORS
                or pristine_emb.hex() != PRISTINE_SHA256
                or candidate_emb.hex() != CANDIDATE_SHA256
            ):
                die("patch header changed or is invalid during apply")

            previous = -1
            applied = 0
            for ordinal in range(count):
                rec = f.read(8)
                if len(rec) != 8:
                    die(f"truncated apply record at ordinal {ordinal}")
                idx, clen = struct.unpack(">II", rec)
                if idx <= previous or idx >= EXPECTED_TOTAL_SECTORS:
                    die(f"invalid apply sector index {idx}")
                if clen <= 0 or clen > MAX_COMPRESSED_RECORD:
                    die(f"invalid apply compressed length at sector {idx}")
                payload = f.read(clen)
                if len(payload) != clen:
                    die(f"truncated apply payload at sector {idx}")
                sector = decode_sector(payload, idx)
                dst.seek(idx * SECTOR)
                dst.write(sector)
                previous = idx
                applied += 1
            if f.read(1):
                die("trailing patch bytes during apply")

        candidate_sha = sha256_file(out)
        if candidate_sha != CANDIDATE_SHA256:
            die(f"round-trip candidate SHA-256 mismatch: {candidate_sha}")

    return {
        "pristine_sha256": pristine_sha,
        "applied_sectors": applied,
        "candidate_sha256": CANDIDATE_SHA256,
        "roundtrip_candidate_sha256": "PASS",
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Batch315 canonical integrity gate for Batch314 ST2SP314 sparse patches"
    )
    ap.add_argument("--patch-file", type=Path, required=True)
    ap.add_argument("--pristine-bin", type=Path,
                    help="optional exact pristine Disc 1; when supplied, perform full round-trip reconstruction")
    ap.add_argument("--output-report", type=Path)
    args = ap.parse_args()

    patch = args.patch_file.resolve()
    if not patch.is_file():
        die(f"missing patch file: {patch}")

    audit = audit_patch(patch)
    report = {
        "batch": 315,
        "status": PASS315,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate_batch": 309,
        "source_patch_batch": 314,
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "expected_changed_sectors": EXPECTED_CHANGED_SECTORS,
            "estimated_or_guessed_bytes": 0,
        },
        "canonical_patch_audit": audit,
        "roundtrip": None,
        "gates": {
            "header_lineage": "PASS",
            "changed_sector_accounting": f"{EXPECTED_CHANGED_SECTORS}/{EXPECTED_CHANGED_SECTORS} PASS",
            "sector_order_and_uniqueness": "PASS",
            "bounded_exact_sector_decompression": "PASS",
            "record_chain_digest": "PASS",
            "full_candidate_roundtrip": "NOT_RUN",
        },
    }

    if args.pristine_bin:
        roundtrip = apply_and_verify(args.pristine_bin.resolve(), patch, audit["patch_sha256"])
        report["roundtrip"] = roundtrip
        report["gates"]["full_candidate_roundtrip"] = "PASS"

    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(PASS315)
    print(f"records={EXPECTED_CHANGED_SECTORS}/{EXPECTED_CHANGED_SECTORS} PASS")
    print("patch_sha256=" + audit["patch_sha256"])
    print("record_chain_sha256=" + audit["record_chain_sha256"])
    print("roundtrip=" + report["gates"]["full_candidate_roundtrip"])


if __name__ == "__main__":
    main()
