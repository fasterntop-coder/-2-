#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zipfile
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
EXPECTED_CHANGED = 90_272
PASS320 = "PASS_B320_REPRODUCIBLE_RELEASE_PACKAGE"
PASS322 = "PASS_B322_RELEASE_PATCH_LEDGER_90272_RECORD_GATE"


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_sums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        if "  " not in raw:
            die(f"malformed SHA256SUMS_RELEASE line {lineno}")
        digest, name = raw.strip().split("  ", 1)
        digest = digest.lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            die(f"invalid SHA-256 on checksum line {lineno}")
        if not name or name in out:
            die(f"duplicate/empty checksum member on line {lineno}")
        out[name] = digest
    return out


def load_release(zf: zipfile.ZipFile) -> tuple[dict, str, str]:
    names = zf.namelist()
    if len(names) != len(set(names)):
        die("duplicate ZIP member names")
    required = {"proof/BATCH320_RELEASE_PACKAGE.json", "SHA256SUMS_RELEASE.txt"}
    if not required.issubset(names):
        die("missing Batch320 proof/checksum members")

    try:
        manifest = json.loads(zf.read("proof/BATCH320_RELEASE_PACKAGE.json").decode("utf-8"))
    except Exception as exc:
        die(f"cannot parse Batch320 manifest: {exc}")
    if not isinstance(manifest, dict) or manifest.get("status") != PASS320:
        die("Batch320 status mismatch")

    lineage = manifest.get("lineage") or {}
    if lineage.get("pristine_sha256") != PRISTINE_SHA256:
        die("pristine SHA lineage mismatch")
    if lineage.get("candidate_sha256") != CANDIDATE_SHA256:
        die("candidate SHA lineage mismatch")
    if lineage.get("changed_sectors") != EXPECTED_CHANGED:
        die("changed-sector lineage mismatch")
    if lineage.get("estimated_or_guessed_bytes") != 0:
        die("guessed bytes are not zero")

    dist = manifest.get("distribution") or {}
    patch_name = dist.get("patch_name")
    ledger_name = dist.get("ledger_name")
    if not isinstance(patch_name, str) or Path(patch_name).name != patch_name:
        die("invalid patch basename")
    if not isinstance(ledger_name, str) or Path(ledger_name).name != ledger_name:
        die("invalid ledger basename")
    patch_member = f"patch/{patch_name}"
    ledger_member = f"ledger/{ledger_name}"
    if patch_member not in names or ledger_member not in names:
        die("declared patch/ledger member missing")

    sums = parse_sums(zf.read("SHA256SUMS_RELEASE.txt").decode("utf-8"))
    for member in (patch_member, ledger_member):
        expected = sums.get(member)
        if expected is None:
            die(f"checksum missing for {member}")
        actual = sha256_bytes(zf.read(member))
        if actual != expected:
            die(f"ZIP member SHA-256 mismatch: {member}")

    if sums[patch_member] != dist.get("patch_sha256"):
        die("patch SHA differs between manifest and SHA256SUMS")
    if sums[ledger_member] != dist.get("ledger_sha256"):
        die("ledger SHA differs between manifest and SHA256SUMS")
    return manifest, patch_member, ledger_member


def parse_ledger(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        die(f"ledger is not UTF-8: {exc}")
    rows: list[dict] = []
    previous = -1
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line:
            die(f"blank ledger row at line {lineno}")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            die(f"invalid ledger JSON at line {lineno}: {exc}")
        if not isinstance(row, dict):
            die(f"ledger row {lineno} is not an object")
        ordinal = row.get("ordinal")
        lba = row.get("lba")
        raw_offset = row.get("raw_offset")
        clen = row.get("compressed_bytes")
        psha = row.get("compressed_sha256")
        ssha = row.get("candidate_sector_sha256")
        if ordinal != len(rows):
            die(f"ledger ordinal mismatch at line {lineno}")
        if not isinstance(lba, int) or lba <= previous:
            die(f"ledger LBA non-increasing/invalid at line {lineno}")
        if lba * SECTOR >= EXPECTED_FILE_SIZE:
            die(f"ledger LBA outside Disc 1 at line {lineno}")
        if raw_offset != lba * SECTOR:
            die(f"ledger raw_offset mismatch at LBA {lba}")
        if not isinstance(clen, int) or clen <= 0:
            die(f"ledger compressed_bytes invalid at LBA {lba}")
        for label, digest in (("compressed_sha256", psha), ("candidate_sector_sha256", ssha)):
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
                die(f"ledger {label} invalid at LBA {lba}")
        rows.append(row)
        previous = lba
    if len(rows) != EXPECTED_CHANGED:
        die(f"ledger row count {len(rows)} != {EXPECTED_CHANGED}")
    return rows


def verify_patch_against_ledger(patch: bytes, rows: list[dict]) -> dict:
    if len(patch) < HEADER_SIZE:
        die("truncated sparse patch header")
    magic, version, sector_size, file_size, count, pristine, candidate = struct.unpack(
        HEADER_FMT, patch[:HEADER_SIZE]
    )
    if magic != MAGIC or version != VERSION:
        die("sparse patch format mismatch")
    if sector_size != SECTOR or file_size != EXPECTED_FILE_SIZE:
        die("sparse patch Disc geometry mismatch")
    if count != EXPECTED_CHANGED:
        die(f"sparse patch record count {count} != {EXPECTED_CHANGED}")
    if pristine.hex() != PRISTINE_SHA256 or candidate.hex() != CANDIDATE_SHA256:
        die("sparse patch embedded SHA lineage mismatch")

    pos = HEADER_SIZE
    previous = -1
    lba_chain = hashlib.sha256()
    decoded_sha_chain = hashlib.sha256()
    ledger_line_chain = hashlib.sha256()
    compressed_total = 0

    for ordinal, ledger in enumerate(rows):
        if pos + 8 > len(patch):
            die(f"truncated record header at ordinal {ordinal}")
        lba, clen = struct.unpack(">II", patch[pos:pos + 8])
        pos += 8
        if lba <= previous:
            die(f"patch LBA non-increasing/duplicate at ordinal {ordinal}")
        if pos + clen > len(patch):
            die(f"truncated compressed payload at LBA {lba}")
        payload = patch[pos:pos + clen]
        pos += clen

        if ledger.get("ordinal") != ordinal or ledger.get("lba") != lba:
            die(f"patch/ledger identity mismatch at ordinal {ordinal}")
        if ledger.get("raw_offset") != lba * SECTOR:
            die(f"patch/ledger raw offset mismatch at LBA {lba}")
        if ledger.get("compressed_bytes") != clen:
            die(f"patch/ledger compressed length mismatch at LBA {lba}")
        psha = sha256_bytes(payload)
        if ledger.get("compressed_sha256") != psha:
            die(f"patch/ledger compressed SHA mismatch at LBA {lba}")

        dobj = zlib.decompressobj()
        try:
            raw = dobj.decompress(payload) + dobj.flush()
        except zlib.error as exc:
            die(f"zlib failure at LBA {lba}: {exc}")
        if dobj.unused_data or dobj.unconsumed_tail:
            die(f"non-canonical zlib payload at LBA {lba}")
        if len(raw) != SECTOR:
            die(f"decoded sector length {len(raw)} at LBA {lba}")
        ssha = sha256_bytes(raw)
        if ledger.get("candidate_sector_sha256") != ssha:
            die(f"patch/ledger candidate sector SHA mismatch at LBA {lba}")

        canonical_line = json.dumps(ledger, sort_keys=True, separators=(",", ":")) + "\n"
        ledger_line_chain.update(canonical_line.encode("utf-8"))
        lba_chain.update(struct.pack(">I", lba))
        decoded_sha_chain.update(bytes.fromhex(ssha))
        compressed_total += clen
        previous = lba

    if pos != len(patch):
        die(f"trailing sparse patch bytes: {len(patch) - pos}")

    return {
        "rows": len(rows),
        "first_lba": rows[0]["lba"],
        "last_lba": rows[-1]["lba"],
        "compressed_payload_bytes": compressed_total,
        "ledger_chain_sha256": ledger_line_chain.hexdigest(),
        "lba_set_sha256": lba_chain.hexdigest(),
        "candidate_sector_sha256_chain": decoded_sha_chain.hexdigest(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch322: independently verify the 90,272-record Batch314 sparse patch against the "
            "Batch316 canonical ledger embedded in a Batch320 release ZIP. No pristine BIN is needed."
        )
    )
    ap.add_argument("--release-zip", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    release_zip = args.release_zip.resolve()
    report_path = args.report.resolve()
    if not release_zip.is_file():
        die(f"release ZIP not found: {release_zip}")
    if report_path.exists():
        die(f"refusing to overwrite report: {report_path}")

    with zipfile.ZipFile(release_zip, "r") as zf:
        manifest, patch_member, ledger_member = load_release(zf)
        patch = zf.read(patch_member)
        ledger_data = zf.read(ledger_member)
        rows = parse_ledger(ledger_data)
        audit = verify_patch_against_ledger(patch, rows)

    dist = manifest.get("distribution") or {}
    if sha256_bytes(ledger_data) != dist.get("ledger_sha256"):
        die("final ledger SHA mismatch")
    if sha256_bytes(patch) != dist.get("patch_sha256"):
        die("final patch SHA mismatch")

    report = {
        "batch": 322,
        "status": PASS322,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate_sha256": CANDIDATE_SHA256,
        "source_release_zip": release_zip.name,
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "patch_batch": 314,
            "ledger_batch": 316,
            "release_batch": 320,
            "estimated_or_guessed_bytes": 0,
        },
        "audit": audit,
        "gates": {
            "release_manifest_lineage": "PASS",
            "release_member_sha256": "PASS",
            "patch_header_geometry": "PASS",
            "patch_ledger_identity": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "compressed_payload_sha256": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "decoded_sector_sha256": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "strictly_increasing_unique_lba": "PASS",
            "all_decoded_payloads_exact_2352": "PASS",
            "trailing_patch_bytes": 0,
            "estimated_or_guessed_bytes": 0,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(PASS322)
    print(f"patch_ledger_records={EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS")
    print(f"ledger_chain_sha256={audit['ledger_chain_sha256']}")
    print(f"lba_set_sha256={audit['lba_set_sha256']}")
    print(f"candidate_sector_sha256_chain={audit['candidate_sector_sha256_chain']}")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
