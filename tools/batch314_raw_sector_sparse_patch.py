#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

SECTOR = 2352
MAGIC = b"ST2SP314"
VERSION = 1
PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED_SECTORS = 90_272
PASS312 = "PASS_B312_BATCH309_UNIFIED_RELEASE_CANDIDATE_GATE"
PASS314 = "PASS_B314_EXACT_RAW_SECTOR_SPARSE_PATCH"


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_batch312(root: Path, pristine: Path, candidate: Path) -> dict:
    gate = root / "tools" / "verify_batch312_release_candidate_gate.py"
    if not gate.is_file():
        die(f"missing Batch312 gate: {gate}")
    with tempfile.TemporaryDirectory(prefix="st2_b314_gate_") as td:
        report = Path(td) / "gate.json"
        cp = subprocess.run(
            [
                sys.executable,
                str(gate),
                "--repo-root", str(root),
                "--pristine-bin", str(pristine),
                "--candidate-bin", str(candidate),
                "--output-report", str(report),
                "--require-physical",
            ],
            text=True,
            capture_output=True,
        )
        if cp.returncode != 0:
            die("Batch312 physical gate failed: " + (cp.stderr or cp.stdout).strip())
        data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("status") != PASS312 or data.get("release_ready") is not True:
        die("Batch312 did not certify release_ready=True")
    return data


def changed_sector_indices(pristine: Path, candidate: Path) -> list[int]:
    if pristine.stat().st_size != candidate.stat().st_size:
        die("BIN sizes differ")
    if pristine.stat().st_size % SECTOR:
        die("BIN size is not a multiple of 2352")
    out: list[int] = []
    with pristine.open("rb") as a, candidate.open("rb") as b:
        index = 0
        while True:
            sa = a.read(SECTOR)
            sb = b.read(SECTOR)
            if not sa:
                break
            if len(sa) != SECTOR or len(sb) != SECTOR:
                die("short raw sector while scanning")
            if sa != sb:
                out.append(index)
            index += 1
    return out


def write_patch(pristine: Path, candidate: Path, patch: Path, indices: list[int]) -> dict:
    # Format: MAGIC(8), version(u32), sector_size(u32), file_size(u64), count(u32),
    # pristine_sha(32 raw), candidate_sha(32 raw), then records:
    # sector_index(u32), compressed_len(u32), zlib(candidate_sector).
    header = struct.pack(
        ">8sIIQI32s32s",
        MAGIC,
        VERSION,
        SECTOR,
        pristine.stat().st_size,
        len(indices),
        bytes.fromhex(PRISTINE_SHA256),
        bytes.fromhex(CANDIDATE_SHA256),
    )
    patch.parent.mkdir(parents=True, exist_ok=True)
    compressed_bytes = 0
    with candidate.open("rb") as src, patch.open("wb") as out:
        out.write(header)
        for idx in indices:
            src.seek(idx * SECTOR)
            sector = src.read(SECTOR)
            if len(sector) != SECTOR:
                die(f"cannot read candidate sector {idx}")
            payload = zlib.compress(sector, level=9)
            out.write(struct.pack(">II", idx, len(payload)))
            out.write(payload)
            compressed_bytes += len(payload)
    return {
        "format": "ST2SP314-v1",
        "sector_size": SECTOR,
        "changed_sectors": len(indices),
        "raw_changed_bytes": len(indices) * SECTOR,
        "compressed_payload_bytes": compressed_bytes,
        "patch_bytes": patch.stat().st_size,
        "patch_sha256": sha256_file(patch),
    }


def read_header(f) -> dict:
    fmt = ">8sIIQI32s32s"
    raw = f.read(struct.calcsize(fmt))
    if len(raw) != struct.calcsize(fmt):
        die("truncated patch header")
    magic, version, sector_size, file_size, count, pristine_sha, candidate_sha = struct.unpack(fmt, raw)
    if magic != MAGIC or version != VERSION or sector_size != SECTOR:
        die("unsupported patch format")
    return {
        "file_size": file_size,
        "count": count,
        "pristine_sha256": pristine_sha.hex(),
        "candidate_sha256": candidate_sha.hex(),
    }


def apply_patch(pristine: Path, patch: Path, output: Path) -> dict:
    if sha256_file(pristine) != PRISTINE_SHA256:
        die("pristine SHA-256 mismatch")
    output.parent.mkdir(parents=True, exist_ok=True)
    with pristine.open("rb") as src, output.open("wb") as dst:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            dst.write(chunk)
    with patch.open("rb") as pf, output.open("r+b") as out:
        hdr = read_header(pf)
        if hdr["file_size"] != output.stat().st_size:
            die("patch target size mismatch")
        if hdr["pristine_sha256"] != PRISTINE_SHA256 or hdr["candidate_sha256"] != CANDIDATE_SHA256:
            die("patch embedded SHA lineage mismatch")
        seen: set[int] = set()
        for _ in range(hdr["count"]):
            rec = pf.read(8)
            if len(rec) != 8:
                die("truncated patch record header")
            idx, clen = struct.unpack(">II", rec)
            if idx in seen:
                die(f"duplicate sector record {idx}")
            seen.add(idx)
            payload = pf.read(clen)
            if len(payload) != clen:
                die(f"truncated payload for sector {idx}")
            try:
                sector = zlib.decompress(payload)
            except zlib.error as exc:
                die(f"zlib failure at sector {idx}: {exc}")
            if len(sector) != SECTOR:
                die(f"decoded sector {idx} length {len(sector)} != {SECTOR}")
            off = idx * SECTOR
            if off + SECTOR > hdr["file_size"]:
                die(f"sector {idx} outside target")
            out.seek(off)
            out.write(sector)
        if pf.read(1):
            die("trailing bytes after final patch record")
    result_sha = sha256_file(output)
    if result_sha != CANDIDATE_SHA256:
        output.unlink(missing_ok=True)
        die("applied output SHA-256 mismatch")
    return {"applied_sectors": len(seen), "output_sha256": result_sha}


def build(args: argparse.Namespace) -> None:
    root = args.repo_root.resolve()
    pristine = args.pristine_bin.resolve()
    candidate = args.candidate_bin.resolve()
    if sha256_file(pristine) != PRISTINE_SHA256:
        die("pristine Disc 1 SHA-256 mismatch")
    if sha256_file(candidate) != CANDIDATE_SHA256:
        die("Batch309 candidate SHA-256 mismatch")

    gate = run_batch312(root, pristine, candidate)
    indices = changed_sector_indices(pristine, candidate)
    if len(indices) != EXPECTED_CHANGED_SECTORS:
        die(f"changed-sector accounting mismatch: {len(indices)} != {EXPECTED_CHANGED_SECTORS}")

    patch_meta = write_patch(pristine, candidate, args.patch_file.resolve(), indices)
    with tempfile.TemporaryDirectory(prefix="st2_b314_apply_") as td:
        rebuilt = Path(td) / "rebuilt.bin"
        apply_meta = apply_patch(pristine, args.patch_file.resolve(), rebuilt)

    manifest = {
        "batch": 314,
        "status": PASS314,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "lineage": {
            "authoritative_batch": 309,
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "batch312_status": gate.get("status"),
            "batch312_release_ready": gate.get("release_ready"),
        },
        "patch": patch_meta,
        "roundtrip": apply_meta,
        "gates": {
            "physical_release_gate": "PASS",
            "changed_sector_accounting": f"{EXPECTED_CHANGED_SECTORS}/{EXPECTED_CHANGED_SECTORS} PASS",
            "roundtrip_candidate_sha256": "PASS",
            "estimated_or_guessed_bytes": 0,
        },
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(PASS314)
    print("changed_sectors=90272")
    print("patch_sha256=" + patch_meta["patch_sha256"])
    print("roundtrip_sha256=" + apply_meta["output_sha256"])


def apply_cmd(args: argparse.Namespace) -> None:
    meta = apply_patch(args.pristine_bin.resolve(), args.patch_file.resolve(), args.output_bin.resolve())
    print(PASS314)
    print("applied_sectors=" + str(meta["applied_sectors"]))
    print("output_sha256=" + meta["output_sha256"])


def verify_cmd(args: argparse.Namespace) -> None:
    patch = args.patch_file.resolve()
    with patch.open("rb") as f:
        hdr = read_header(f)
        if hdr["count"] != EXPECTED_CHANGED_SECTORS:
            die(f"patch record count mismatch: {hdr['count']}")
        if hdr["pristine_sha256"] != PRISTINE_SHA256 or hdr["candidate_sha256"] != CANDIDATE_SHA256:
            die("patch lineage mismatch")
        seen: set[int] = set()
        for _ in range(hdr["count"]):
            rec = f.read(8)
            if len(rec) != 8:
                die("truncated patch")
            idx, clen = struct.unpack(">II", rec)
            if idx in seen:
                die(f"duplicate sector {idx}")
            seen.add(idx)
            payload = f.read(clen)
            if len(payload) != clen or len(zlib.decompress(payload)) != SECTOR:
                die(f"bad payload at sector {idx}")
        if f.read(1):
            die("trailing patch bytes")
    print(PASS314)
    print("records=90272/90272 PASS")
    print("patch_sha256=" + sha256_file(patch))


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch314 exact 32-bit raw-sector sparse patch builder/apply/verifier")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="physically gate Batch309 and emit an exact sparse patch")
    b.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    b.add_argument("--pristine-bin", type=Path, required=True)
    b.add_argument("--candidate-bin", type=Path, required=True)
    b.add_argument("--patch-file", type=Path, required=True)
    b.add_argument("--manifest", type=Path)
    b.set_defaults(func=build)

    a = sub.add_parser("apply", help="apply sparse patch to exact pristine Disc 1 and verify candidate SHA")
    a.add_argument("--pristine-bin", type=Path, required=True)
    a.add_argument("--patch-file", type=Path, required=True)
    a.add_argument("--output-bin", type=Path, required=True)
    a.set_defaults(func=apply_cmd)

    v = sub.add_parser("verify", help="verify sparse patch structure, lineage and all sector payloads")
    v.add_argument("--patch-file", type=Path, required=True)
    v.set_defaults(func=verify_cmd)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
