#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

MAGIC = b"ST2SP314"
VERSION = 1
HEADER_FMT = ">8sIIQI32s32s"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

DISC_SIZE = 659_293_824
TOTAL_SECTORS = 280_312
TRACK01_SECTORS = 278_722
TRACK02_SECTORS = 1_590
TRACK02_START_LBA = TRACK01_SECTORS
EXPECTED_CHANGED = 90_272
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
PASS = "PASS_B324_TRACK01_FULL_EDC_ECC_TRACK02_AUDIO_BYTE_IDENTITY"


def die(message: str) -> None:
    raise SystemExit("FAIL " + message)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_changed_lbas(path: Path) -> tuple[list[int], str]:
    lbas: list[int] = []
    chain = hashlib.sha256()
    with path.open("rb") as f:
        header = f.read(HEADER_SIZE)
        if len(header) != HEADER_SIZE:
            die("truncated sparse-patch header")
        magic, version, sector_size, file_size, count, pristine, candidate = struct.unpack(HEADER_FMT, header)
        if magic != MAGIC or version != VERSION:
            die("sparse-patch magic/version mismatch")
        if sector_size != RAW_SECTOR_SIZE or file_size != DISC_SIZE or count != EXPECTED_CHANGED:
            die("sparse-patch geometry/count mismatch")
        if pristine.hex() != PRISTINE_SHA256 or candidate.hex() != CANDIDATE_SHA256:
            die("sparse-patch lineage SHA mismatch")

        previous = -1
        for ordinal in range(count):
            rec = f.read(8)
            if len(rec) != 8:
                die(f"truncated patch record {ordinal}")
            lba, compressed_len = struct.unpack(">II", rec)
            if lba <= previous:
                die(f"duplicate/nonascending LBA {lba}")
            if lba >= TOTAL_SECTORS:
                die(f"out-of-range LBA {lba}")
            if lba >= TRACK02_START_LBA:
                die(f"patch touches Track02 audio LBA {lba}")
            payload = f.read(compressed_len)
            if len(payload) != compressed_len:
                die(f"truncated payload LBA {lba}")
            try:
                raw = zlib.decompress(payload)
            except zlib.error as exc:
                die(f"zlib failure LBA {lba}: {exc}")
            if len(raw) != RAW_SECTOR_SIZE:
                die(f"decoded sector size mismatch LBA {lba}")
            chain.update(struct.pack(">I", lba))
            chain.update(hashlib.sha256(raw).digest())
            lbas.append(lba)
            previous = lba
        if f.read(1):
            die("trailing sparse-patch bytes")

    if len(lbas) != EXPECTED_CHANGED:
        die("changed LBA count mismatch")
    return lbas, chain.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch324: authoritative Disc1 full-track integrity gate. Proves that all 90,272 patch records "
            "remain inside Track01, validates MODE1/2352 EDC/ECC for every one of Track01's 278,722 sectors, "
            "and proves all 1,590 Track02 audio sectors are byte-identical between pristine and candidate."
        )
    )
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--patch-file", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    for p in (args.pristine_bin, args.candidate_bin, args.patch_file):
        if not p.is_file():
            die(f"missing input {p}")
    if args.report.exists():
        die("refusing to overwrite report")
    if args.pristine_bin.stat().st_size != DISC_SIZE or args.candidate_bin.stat().st_size != DISC_SIZE:
        die("Disc size mismatch")

    pristine_sha = sha256_file(args.pristine_bin)
    candidate_sha = sha256_file(args.candidate_bin)
    if pristine_sha != PRISTINE_SHA256:
        die(f"pristine SHA mismatch {pristine_sha}")
    if candidate_sha != CANDIDATE_SHA256:
        die(f"candidate SHA mismatch {candidate_sha}")

    changed_lbas, changed_chain = parse_changed_lbas(args.patch_file)
    changed_set = set(changed_lbas)

    track01_bad: list[dict[str, object]] = []
    track01_changed_seen = 0
    track01_unchanged_seen = 0
    audio_mismatch_lbas: list[int] = []
    audio_chain_pristine = hashlib.sha256()
    audio_chain_candidate = hashlib.sha256()
    track01_candidate_chain = hashlib.sha256()

    with args.pristine_bin.open("rb") as pristine, args.candidate_bin.open("rb") as candidate:
        for lba in range(TOTAL_SECTORS):
            p = pristine.read(RAW_SECTOR_SIZE)
            c = candidate.read(RAW_SECTOR_SIZE)
            if len(p) != RAW_SECTOR_SIZE or len(c) != RAW_SECTOR_SIZE:
                die(f"short Disc read LBA {lba}")

            if lba < TRACK01_SECTORS:
                verification = verify_mode1_sector(c)
                if not verification.get("valid"):
                    if len(track01_bad) < 32:
                        track01_bad.append({"lba": lba, "verification": verification})
                track01_candidate_chain.update(struct.pack(">I", lba))
                track01_candidate_chain.update(hashlib.sha256(c).digest())

                if lba in changed_set:
                    if p == c:
                        die(f"patch-declared changed Track01 sector is byte-identical LBA {lba}")
                    track01_changed_seen += 1
                else:
                    if p != c:
                        die(f"undeclared Track01 change LBA {lba}")
                    track01_unchanged_seen += 1
            else:
                if p != c and len(audio_mismatch_lbas) < 32:
                    audio_mismatch_lbas.append(lba)
                audio_chain_pristine.update(p)
                audio_chain_candidate.update(c)

        if pristine.read(1) or candidate.read(1):
            die("unexpected trailing Disc bytes")

    if track01_bad:
        die(f"Track01 EDC/ECC failures: {len(track01_bad)} examples={track01_bad[:4]}")
    if track01_changed_seen != EXPECTED_CHANGED:
        die(f"Track01 changed count mismatch {track01_changed_seen}")
    expected_track01_unchanged = TRACK01_SECTORS - EXPECTED_CHANGED
    if track01_unchanged_seen != expected_track01_unchanged:
        die(f"Track01 unchanged count mismatch {track01_unchanged_seen}")
    if audio_mismatch_lbas:
        die(f"Track02 audio differs at LBAs {audio_mismatch_lbas[:16]}")

    audio_pristine_sha = audio_chain_pristine.hexdigest()
    audio_candidate_sha = audio_chain_candidate.hexdigest()
    if audio_pristine_sha != audio_candidate_sha:
        die("Track02 aggregate SHA mismatch")

    report = {
        "batch": 324,
        "status": PASS,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "sparse_patch_batch": 314,
            "full_disc_accounting_batch": 323,
            "estimated_or_guessed_bytes": 0,
        },
        "disc_geometry": {
            "disc_bytes": DISC_SIZE,
            "raw_sector_bytes": RAW_SECTOR_SIZE,
            "total_sectors": TOTAL_SECTORS,
            "track01": {"type": "MODE1/2352", "start_lba": 0, "sectors": TRACK01_SECTORS},
            "track02": {"type": "AUDIO", "start_lba": TRACK02_START_LBA, "sectors": TRACK02_SECTORS},
        },
        "patch_scope": {
            "changed_records": len(changed_lbas),
            "changed_track01": track01_changed_seen,
            "changed_track02": 0,
            "changed_lba_sector_chain_sha256": changed_chain,
        },
        "track01_gate": {
            "edc_ecc_checked": TRACK01_SECTORS,
            "edc_ecc_valid": TRACK01_SECTORS,
            "edc_ecc_bad": 0,
            "declared_changed": track01_changed_seen,
            "declared_unchanged": track01_unchanged_seen,
            "undeclared_changes": 0,
            "candidate_lba_sector_chain_sha256": track01_candidate_chain.hexdigest(),
        },
        "track02_gate": {
            "audio_sectors_checked": TRACK02_SECTORS,
            "byte_identical": TRACK02_SECTORS,
            "mismatched": 0,
            "pristine_audio_sha256": audio_pristine_sha,
            "candidate_audio_sha256": audio_candidate_sha,
        },
        "gates": {
            "pristine_full_sha256": "PASS",
            "candidate_full_sha256": "PASS",
            "patch_all_changes_inside_track01": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "track01_full_edc_ecc": f"{TRACK01_SECTORS}/{TRACK01_SECTORS} PASS",
            "track01_change_declaration_accounting": f"{TRACK01_SECTORS}/{TRACK01_SECTORS} PASS",
            "track02_audio_byte_identity": f"{TRACK02_SECTORS}/{TRACK02_SECTORS} PASS",
            "estimated_or_guessed_bytes": 0,
        },
        "hardware_validation": "PENDING; full byte/track/MODE1 integrity gate only",
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(PASS)
    print(f"track01_edc_ecc={TRACK01_SECTORS}/{TRACK01_SECTORS} PASS")
    print(f"track01_changed={track01_changed_seen} track01_unchanged={track01_unchanged_seen}")
    print(f"track02_audio_byte_identity={TRACK02_SECTORS}/{TRACK02_SECTORS} PASS")
    print(f"candidate_sha256={candidate_sha}")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
