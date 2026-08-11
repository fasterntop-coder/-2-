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
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED = 90_272
SUCCESS = "PASS_B317_CANONICAL_90272_SECTOR_EDCECC_LEDGER_ROUNDTRIP"


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ledger(path: Path) -> list[dict]:
    rows: list[dict] = []
    previous = -1
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                die(f"blank ledger line {lineno}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                die(f"invalid ledger JSON line {lineno}: {e}")
            expected_ordinal = len(rows)
            if row.get("ordinal") != expected_ordinal:
                die(f"ledger ordinal line {lineno}: {row.get('ordinal')} != {expected_ordinal}")
            lba = row.get("lba")
            if not isinstance(lba, int) or lba <= previous:
                die(f"ledger LBA is duplicate/non-increasing at line {lineno}")
            if row.get("raw_offset") != lba * RAW_SECTOR_SIZE:
                die(f"ledger raw_offset mismatch at LBA {lba}")
            if not isinstance(row.get("compressed_bytes"), int) or row["compressed_bytes"] <= 0:
                die(f"ledger compressed_bytes invalid at LBA {lba}")
            for key in ("compressed_sha256", "candidate_sector_sha256"):
                value = row.get(key)
                if not isinstance(value, str) or len(value) != 64:
                    die(f"ledger {key} invalid at LBA {lba}")
            previous = lba
            rows.append(row)
    if len(rows) != EXPECTED_CHANGED:
        die(f"ledger rows {len(rows)} != {EXPECTED_CHANGED}")
    return rows


def parse_and_verify_patch(patch: Path, ledger_rows: list[dict]) -> tuple[dict[int, bytes], dict]:
    changed: dict[int, bytes] = {}
    invalid_lbas: list[int] = []
    component_failures = {"sync": 0, "mode": 0, "edc": 0, "reserved": 0, "ecc_p": 0, "ecc_q": 0}
    record_chain = hashlib.sha256()
    lba_chain = hashlib.sha256()
    decoded_chain = hashlib.sha256()
    compressed_total = 0

    with patch.open("rb") as f:
        header = f.read(HEADER_SIZE)
        if len(header) != HEADER_SIZE:
            die("truncated patch header")
        magic, version, sector_size, file_size, count, pristine, candidate = struct.unpack(HEADER_FMT, header)
        if magic != MAGIC or version != VERSION:
            die("patch format/version mismatch")
        if sector_size != RAW_SECTOR_SIZE or file_size != DISC_SIZE:
            die("patch Disc geometry mismatch")
        if count != EXPECTED_CHANGED:
            die(f"patch changed-sector count {count} != {EXPECTED_CHANGED}")
        if pristine.hex() != PRISTINE_SHA256 or candidate.hex() != CANDIDATE_SHA256:
            die("patch SHA lineage mismatch")

        previous = -1
        for ordinal in range(count):
            rec = f.read(8)
            if len(rec) != 8:
                die(f"truncated patch record {ordinal}")
            lba, clen = struct.unpack(">II", rec)
            if lba <= previous:
                die(f"patch duplicate/non-increasing LBA {lba}")
            if lba * RAW_SECTOR_SIZE >= DISC_SIZE:
                die(f"patch LBA outside Disc 1: {lba}")
            if clen <= 0 or clen > 8192:
                die(f"invalid compressed length at LBA {lba}: {clen}")
            payload = f.read(clen)
            if len(payload) != clen:
                die(f"truncated compressed payload at LBA {lba}")
            try:
                raw = zlib.decompress(payload)
            except zlib.error as e:
                die(f"zlib decode failed at LBA {lba}: {e}")
            if len(raw) != RAW_SECTOR_SIZE:
                die(f"decoded sector length {len(raw)} at LBA {lba}")

            row = ledger_rows[ordinal]
            psha = hashlib.sha256(payload).hexdigest()
            ssha = hashlib.sha256(raw).hexdigest()
            exact = {
                "ordinal": ordinal,
                "lba": lba,
                "raw_offset": lba * RAW_SECTOR_SIZE,
                "compressed_bytes": clen,
                "compressed_sha256": psha,
                "candidate_sector_sha256": ssha,
            }
            for key, value in exact.items():
                if row.get(key) != value:
                    die(f"ledger/patch mismatch at ordinal {ordinal} key {key}")

            check = verify_mode1_sector(raw)
            if not check.get("valid"):
                invalid_lbas.append(lba)
                for key in component_failures:
                    if not check.get(key):
                        component_failures[key] += 1

            canonical_line = json.dumps(exact, sort_keys=True, separators=(",", ":")) + "\n"
            record_chain.update(canonical_line.encode("utf-8"))
            lba_chain.update(struct.pack(">I", lba))
            decoded_chain.update(bytes.fromhex(ssha))
            compressed_total += clen
            changed[lba] = raw
            previous = lba

        if f.read(1):
            die("trailing patch bytes")

    if len(changed) != EXPECTED_CHANGED:
        die(f"unique changed sectors {len(changed)} != {EXPECTED_CHANGED}")
    if invalid_lbas:
        die(f"MODE1 EDC/ECC invalid sectors: count={len(invalid_lbas)} examples={invalid_lbas[:16]}")

    return changed, {
        "record_chain_sha256": record_chain.hexdigest(),
        "lba_set_sha256": lba_chain.hexdigest(),
        "candidate_sector_sha256_chain": decoded_chain.hexdigest(),
        "compressed_payload_bytes": compressed_total,
        "mode1_edc_ecc": f"{len(changed)}/{EXPECTED_CHANGED} PASS",
        "component_failures": component_failures,
    }


def reconstruct_candidate_sha(pristine: Path, changed: dict[int, bytes]) -> str:
    if pristine.stat().st_size != DISC_SIZE:
        die(f"pristine Disc size {pristine.stat().st_size} != {DISC_SIZE}")
    if sha256_file(pristine) != PRISTINE_SHA256:
        die("pristine full SHA-256 mismatch")

    h = hashlib.sha256()
    applied = 0
    with pristine.open("rb") as src:
        for lba in range(DISC_SIZE // RAW_SECTOR_SIZE):
            original = src.read(RAW_SECTOR_SIZE)
            if len(original) != RAW_SECTOR_SIZE:
                die(f"short pristine read at LBA {lba}")
            replacement = changed.get(lba)
            if replacement is None:
                h.update(original)
            else:
                if replacement == original:
                    die(f"patch sector at LBA {lba} is identical to pristine")
                h.update(replacement)
                applied += 1
        if src.read(1):
            die("pristine has unexpected trailing byte")
    if applied != EXPECTED_CHANGED:
        die(f"roundtrip applied sectors {applied} != {EXPECTED_CHANGED}")
    digest = h.hexdigest()
    if digest != CANDIDATE_SHA256:
        die(f"reconstructed candidate SHA-256 {digest} != {CANDIDATE_SHA256}")
    return digest


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Batch317: cross-check Batch316 canonical ledger against every Batch314 sparse record, verify MODE1/2352 EDC/ECC on all 90,272 candidate sectors, and optionally reconstruct the full Batch309 candidate SHA from pristine Disc 1."
    )
    ap.add_argument("--patch-file", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--output-report", type=Path, required=True)
    ap.add_argument("--pristine-bin", type=Path)
    args = ap.parse_args()

    for p in (args.patch_file, args.ledger):
        if not p.is_file():
            die(f"missing input {p}")
    if args.pristine_bin is not None and not args.pristine_bin.is_file():
        die(f"missing pristine BIN {args.pristine_bin}")

    rows = load_ledger(args.ledger)
    ledger_sha = sha256_file(args.ledger)
    patch_sha = sha256_file(args.patch_file)
    changed, patch_result = parse_and_verify_patch(args.patch_file, rows)

    reconstructed_sha = None
    roundtrip = "NOT_RUN"
    if args.pristine_bin is not None:
        reconstructed_sha = reconstruct_candidate_sha(args.pristine_bin, changed)
        roundtrip = "PASS"

    report = {
        "batch": 317,
        "status": SUCCESS,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate_batch": 309,
        "inputs": {
            "source_patch_batch": 314,
            "canonical_ledger_batch": 316,
            "patch_sha256": patch_sha,
            "ledger_sha256": ledger_sha,
        },
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "estimated_or_guessed_bytes": 0,
        },
        "gates": {
            "ledger_rows": f"{len(rows)}/{EXPECTED_CHANGED} PASS",
            "patch_records": f"{len(changed)}/{EXPECTED_CHANGED} PASS",
            "ledger_patch_exact_crosscheck": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "changed_sector_mode1_edc_ecc": patch_result["mode1_edc_ecc"],
            "mode1_component_failures": patch_result["component_failures"],
            "strict_unique_increasing_lba": "PASS",
            "all_payloads_exact_2352": "PASS",
            "trailing_patch_bytes": 0,
            "estimated_or_guessed_bytes": 0,
            "full_candidate_roundtrip": roundtrip,
        },
        "chains": {
            "record_chain_sha256": patch_result["record_chain_sha256"],
            "lba_set_sha256": patch_result["lba_set_sha256"],
            "candidate_sector_sha256_chain": patch_result["candidate_sector_sha256_chain"],
            "compressed_payload_bytes": patch_result["compressed_payload_bytes"],
        },
        "reconstructed_candidate_sha256": reconstructed_sha,
        "hardware_validation": "PENDING; this gate certifies exact bytes and MODE1/2352 integrity, not playback behavior",
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(SUCCESS)
    print(f"ledger_patch_exact_crosscheck={EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS")
    print(f"changed_sector_mode1_edc_ecc={EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS")
    print(f"full_candidate_roundtrip={roundtrip}")


if __name__ == "__main__":
    main()
