#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path

SECTOR = 2352
MAGIC = b"ST2SP314"
VERSION = 1
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED = 90_272
PASS320 = "PASS_B320_REPRODUCIBLE_RELEASE_PACKAGE"
PASS321 = "PASS_B321_STANDALONE_RELEASE_PACKAGE_APPLY"
HEADER_FMT = ">8sIIQI32s32s"
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_stream(f) -> str:
    h = hashlib.sha256()
    for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
        h.update(chunk)
    return h.hexdigest()


def parse_sums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if "  " not in line:
            die(f"malformed SHA256SUMS_RELEASE line {lineno}")
        digest, name = line.split("  ", 1)
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            die(f"invalid SHA-256 on line {lineno}")
        if not name or name in out:
            die(f"duplicate/empty checksum member on line {lineno}")
        out[name] = digest.lower()
    return out


def validate_zip(zf: zipfile.ZipFile) -> tuple[dict, str, str, str]:
    names = zf.namelist()
    if len(names) != len(set(names)):
        die("release ZIP contains duplicate member names")
    required = {"proof/BATCH320_RELEASE_PACKAGE.json", "SHA256SUMS_RELEASE.txt"}
    missing = required - set(names)
    if missing:
        die("release ZIP missing required members: " + ", ".join(sorted(missing)))

    try:
        manifest = json.loads(zf.read("proof/BATCH320_RELEASE_PACKAGE.json").decode("utf-8"))
    except Exception as exc:
        die(f"cannot parse Batch320 release manifest: {exc}")
    if not isinstance(manifest, dict) or manifest.get("status") != PASS320:
        die("Batch320 release manifest status mismatch")

    lineage = manifest.get("lineage") or {}
    if lineage.get("pristine_sha256") != PRISTINE_SHA256:
        die("release pristine SHA lineage mismatch")
    if lineage.get("candidate_sha256") != CANDIDATE_SHA256:
        die("release candidate SHA lineage mismatch")
    if lineage.get("changed_sectors") != EXPECTED_CHANGED:
        die("release changed-sector lineage mismatch")
    if lineage.get("estimated_or_guessed_bytes") != 0:
        die("release lineage contains guessed bytes")

    dist = manifest.get("distribution") or {}
    patch_name = dist.get("patch_name")
    cue_name = dist.get("candidate_cue_name")
    ledger_name = dist.get("ledger_name")
    if not all(isinstance(x, str) and x and Path(x).name == x for x in (patch_name, cue_name, ledger_name)):
        die("release manifest contains invalid member basenames")
    patch_member = f"patch/{patch_name}"
    cue_member = f"candidate/{cue_name}"
    ledger_member = f"ledger/{ledger_name}"
    for member in (patch_member, cue_member, ledger_member):
        if member not in names:
            die(f"release ZIP missing declared member: {member}")

    sums = parse_sums(zf.read("SHA256SUMS_RELEASE.txt").decode("utf-8"))
    for member in names:
        if member == "SHA256SUMS_RELEASE.txt":
            continue
        expected = sums.get(member)
        if expected is None:
            die(f"release member has no SHA256SUMS entry: {member}")
        with zf.open(member, "r") as f:
            actual = sha256_stream(f)
        if actual != expected:
            die(f"release member SHA-256 mismatch: {member}")

    if sums.get(patch_member) != dist.get("patch_sha256"):
        die("patch SHA differs between release manifest and checksum ledger")
    if sums.get(cue_member) != dist.get("candidate_cue_sha256"):
        die("CUE SHA differs between release manifest and checksum ledger")
    if sums.get(ledger_member) != dist.get("ledger_sha256"):
        die("ledger SHA differs between release manifest and checksum ledger")

    not_included = [k for k, v in sums.items() if k.startswith("NOT_INCLUDED/") and v == CANDIDATE_SHA256]
    if len(not_included) != 1:
        die("release checksum ledger does not uniquely bind the omitted candidate BIN SHA")

    return manifest, patch_member, cue_member, ledger_member


def read_patch_header(pf) -> dict:
    raw = pf.read(HEADER_SIZE)
    if len(raw) != HEADER_SIZE:
        die("truncated sparse patch header")
    magic, version, sector_size, file_size, count, pristine_sha, candidate_sha = struct.unpack(HEADER_FMT, raw)
    if magic != MAGIC or version != VERSION or sector_size != SECTOR:
        die("unsupported sparse patch format")
    if count != EXPECTED_CHANGED:
        die(f"sparse patch record count mismatch: {count} != {EXPECTED_CHANGED}")
    if pristine_sha.hex() != PRISTINE_SHA256 or candidate_sha.hex() != CANDIDATE_SHA256:
        die("sparse patch embedded SHA lineage mismatch")
    return {"file_size": file_size, "count": count}


def apply_from_zip(pristine: Path, zf: zipfile.ZipFile, patch_member: str, output_bin: Path) -> dict:
    if sha256_file(pristine) != PRISTINE_SHA256:
        die("pristine Disc 1 SHA-256 mismatch")

    output_bin.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=output_bin.name + ".", suffix=".tmp", dir=output_bin.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copyfile(pristine, tmp)
        with zf.open(patch_member, "r") as pf, tmp.open("r+b") as out:
            hdr = read_patch_header(pf)
            if hdr["file_size"] != tmp.stat().st_size:
                die("patch target size mismatch")
            seen: set[int] = set()
            previous = -1
            for ordinal in range(hdr["count"]):
                rec = pf.read(8)
                if len(rec) != 8:
                    die(f"truncated patch record header at ordinal {ordinal}")
                idx, clen = struct.unpack(">II", rec)
                if idx in seen:
                    die(f"duplicate sector record {idx}")
                if idx <= previous:
                    die(f"non-canonical sector ordering at {idx}")
                seen.add(idx)
                previous = idx
                if clen <= 0:
                    die(f"invalid compressed length at sector {idx}")
                payload = pf.read(clen)
                if len(payload) != clen:
                    die(f"truncated payload for sector {idx}")
                dobj = zlib.decompressobj()
                try:
                    sector = dobj.decompress(payload) + dobj.flush()
                except zlib.error as exc:
                    die(f"zlib failure at sector {idx}: {exc}")
                if dobj.unused_data or dobj.unconsumed_tail:
                    die(f"non-canonical zlib payload at sector {idx}")
                if len(sector) != SECTOR:
                    die(f"decoded sector {idx} length {len(sector)} != {SECTOR}")
                off = idx * SECTOR
                if off + SECTOR > hdr["file_size"]:
                    die(f"sector {idx} outside target")
                out.seek(off)
                out.write(sector)
            if pf.read(1):
                die("trailing bytes after final sparse patch record")

        actual = sha256_file(tmp)
        if actual != CANDIDATE_SHA256:
            die("materialized candidate BIN SHA-256 mismatch")
        if len(seen) != EXPECTED_CHANGED:
            die("changed-sector accounting mismatch after apply")
        if output_bin.exists():
            die(f"refusing to overwrite existing output BIN: {output_bin}")
        tmp.replace(output_bin)
        return {"applied_sectors": len(seen), "output_sha256": actual}
    finally:
        tmp.unlink(missing_ok=True)


def extract_cue(zf: zipfile.ZipFile, cue_member: str, output_cue: Path) -> str:
    if output_cue.exists():
        die(f"refusing to overwrite existing output CUE: {output_cue}")
    data = zf.read(cue_member)
    output_cue.parent.mkdir(parents=True, exist_ok=True)
    output_cue.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch321: standalone consumer for the deterministic Batch320 release ZIP. "
            "Given only the exact pristine Disc 1 BIN and the release package, verify every packaged member, "
            "apply all 90,272 canonical raw sectors, and materialize the exact candidate BIN/CUE."
        )
    )
    ap.add_argument("--release-zip", type=Path, required=True)
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--output-bin-name", default="Sakura_Taisen_2_Disc1_KR_B321.bin")
    args = ap.parse_args()

    release_zip = args.release_zip.resolve()
    pristine = args.pristine_bin.resolve()
    output_dir = args.output_dir.resolve()
    if not release_zip.is_file():
        die(f"release ZIP not found: {release_zip}")
    if not pristine.is_file():
        die(f"pristine BIN not found: {pristine}")
    if Path(args.output_bin_name).name != args.output_bin_name or not args.output_bin_name.lower().endswith(".bin"):
        die("--output-bin-name must be a simple .bin basename")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_bin = output_dir / args.output_bin_name

    with zipfile.ZipFile(release_zip, "r") as zf:
        manifest, patch_member, cue_member, _ledger_member = validate_zip(zf)
        meta = apply_from_zip(pristine, zf, patch_member, output_bin)

        original_cue_name = Path(cue_member).name
        output_cue = output_dir / (Path(args.output_bin_name).stem + ".cue")
        cue_text = zf.read(cue_member).decode("utf-8", errors="strict")
        declared_old_bin = (manifest.get("distribution") or {}).get("candidate_bin_name")
        if not isinstance(declared_old_bin, str) or Path(declared_old_bin).name != declared_old_bin:
            output_bin.unlink(missing_ok=True)
            die("invalid candidate BIN name in Batch320 manifest")
        old_token = declared_old_bin
        replacements = cue_text.count(old_token)
        if replacements != 1:
            output_bin.unlink(missing_ok=True)
            die(f"CUE does not contain exactly one declared BIN reference: {replacements}")
        cue_text = cue_text.replace(old_token, args.output_bin_name, 1)
        if output_cue.exists():
            output_bin.unlink(missing_ok=True)
            die(f"refusing to overwrite existing output CUE: {output_cue}")
        output_cue.write_text(cue_text, encoding="utf-8", newline="")
        cue_sha = sha256_file(output_cue)

    report = {
        "batch": 321,
        "status": PASS321,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "input": {
            "release_zip": release_zip.name,
            "release_zip_sha256": sha256_file(release_zip),
            "pristine_sha256": PRISTINE_SHA256,
        },
        "output": {
            "bin": output_bin.name,
            "bin_sha256": meta["output_sha256"],
            "cue": output_cue.name,
            "cue_sha256": cue_sha,
            "source_packaged_cue": original_cue_name,
        },
        "gates": {
            "batch320_package_all_members_sha256": "PASS",
            "pristine_full_sha256": "PASS",
            "sparse_patch_lineage": "PASS",
            "changed_sector_accounting": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "candidate_full_sha256": "PASS",
            "cue_retarget_exact_single_reference": "PASS",
            "estimated_or_guessed_bytes": 0,
        },
    }
    report_path = output_dir / "BATCH321_STANDALONE_APPLY.json"
    if report_path.exists():
        output_bin.unlink(missing_ok=True)
        output_cue.unlink(missing_ok=True)
        die(f"refusing to overwrite existing report: {report_path}")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(PASS321)
    print(f"output_bin={output_bin}")
    print(f"output_bin_sha256={meta['output_sha256']}")
    print(f"output_cue={output_cue}")
    print(f"changed_sectors={meta['applied_sectors']}/{EXPECTED_CHANGED} PASS")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
