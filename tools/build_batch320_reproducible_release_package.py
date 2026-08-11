#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED = 90_272
PASS319 = "PASS_B319_MATERIALIZED_BIN_CUE_CANDIDATE_PACK"
PASS320 = "PASS_B320_REPRODUCIBLE_RELEASE_PACKAGE"
FIXED_ZIP_TIME = (2026, 8, 12, 0, 0, 0)


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"cannot parse JSON {path}: {exc}")
    if not isinstance(obj, dict):
        die(f"JSON root must be object: {path}")
    return obj


def validate_batch319(pack_dir: Path) -> tuple[Path, Path, dict]:
    manifest_path = pack_dir / "BATCH319_MATERIALIZED_BIN_CUE_CANDIDATE.json"
    if not manifest_path.is_file():
        die(f"missing Batch319 manifest: {manifest_path}")
    manifest = load_json(manifest_path)
    if manifest.get("status") != PASS319:
        die("Batch319 status mismatch")

    lineage = manifest.get("lineage") or {}
    if lineage.get("pristine_sha256") != PRISTINE_SHA256:
        die("Batch319 pristine SHA-256 lineage mismatch")
    if lineage.get("candidate_sha256") != CANDIDATE_SHA256:
        die("Batch319 candidate SHA-256 lineage mismatch")
    if lineage.get("changed_sectors") != EXPECTED_CHANGED:
        die("Batch319 changed-sector lineage mismatch")
    if lineage.get("estimated_or_guessed_bytes") != 0:
        die("Batch319 contains estimated/guessed bytes")
    if lineage.get("guessed_cue_layout") is not False:
        die("Batch319 CUE layout is not proven exact")

    out = manifest.get("output") or {}
    bin_name = out.get("bin")
    cue_name = out.get("cue")
    if not isinstance(bin_name, str) or not bin_name:
        die("Batch319 output BIN name missing")
    if not isinstance(cue_name, str) or not cue_name:
        die("Batch319 output CUE name missing")
    if Path(bin_name).name != bin_name or Path(cue_name).name != cue_name:
        die("Batch319 output names must be basenames")

    candidate_bin = pack_dir / bin_name
    candidate_cue = pack_dir / cue_name
    if not candidate_bin.is_file():
        die(f"missing materialized candidate BIN: {candidate_bin}")
    if not candidate_cue.is_file():
        die(f"missing materialized candidate CUE: {candidate_cue}")
    if sha256_file(candidate_bin) != CANDIDATE_SHA256:
        die("materialized candidate BIN SHA-256 mismatch")
    if out.get("bin_sha256") != CANDIDATE_SHA256:
        die("Batch319 manifest BIN SHA-256 mismatch")
    actual_cue_sha = sha256_file(candidate_cue)
    if out.get("cue_sha256") != actual_cue_sha:
        die("Batch319 manifest CUE SHA-256 mismatch")

    gates = manifest.get("gates") or {}
    required_pass = (
        "batch318_materialization",
        "candidate_full_bin_sha256",
        "source_cue_track_layout_preserved",
        "cue_file_reference_retargeted",
    )
    for key in required_pass:
        if gates.get(key) != "PASS":
            die(f"Batch319 gate not PASS: {key}")
    if gates.get("estimated_or_guessed_bytes") != 0:
        die("Batch319 gate reports guessed bytes")

    return candidate_bin, candidate_cue, manifest


def validate_required_sidecars(pack_dir: Path) -> list[Path]:
    names = [
        "BATCH317_PHYSICAL_GATE.json",
        "BATCH318_MATERIALIZED_CD1_CANDIDATE.json",
        "BATCH319_MATERIALIZED_BIN_CUE_CANDIDATE.json",
        "SHA256SUMS.txt",
    ]
    paths = [pack_dir / name for name in names]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        die("missing Batch319 sidecars: " + ", ".join(missing))
    return paths


def zip_write_file(zf: zipfile.ZipFile, source: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    with source.open("rb") as src, zf.open(info, "w", force_zip64=True) as dst:
        for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
            dst.write(chunk)


def zip_write_bytes(zf: zipfile.ZipFile, data: bytes, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (0o100644 & 0xFFFF) << 16
    zf.writestr(info, data)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch320: seal an already materialized and fully verified Batch319 Disc 1 BIN/CUE candidate "
            "into a deterministic release archive. The archive contains the candidate CUE, physical gate "
            "manifests, canonical sparse patch and sector ledger, but intentionally omits the full BIN. "
            "No byte/layout inference is performed."
        )
    )
    ap.add_argument("--batch319-dir", type=Path, required=True)
    ap.add_argument("--patch-file", type=Path, required=True, help="Batch314 canonical sparse patch")
    ap.add_argument("--ledger", type=Path, required=True, help="Batch316 canonical changed-sector ledger")
    ap.add_argument("--output-zip", type=Path, required=True)
    args = ap.parse_args()

    pack_dir = args.batch319_dir.resolve()
    patch = args.patch_file.resolve()
    ledger = args.ledger.resolve()
    output_zip = args.output_zip.resolve()

    if not pack_dir.is_dir():
        die(f"Batch319 directory not found: {pack_dir}")
    for p, label in ((patch, "Batch314 sparse patch"), (ledger, "Batch316 ledger")):
        if not p.is_file():
            die(f"missing {label}: {p}")
    if output_zip.exists():
        die(f"refusing to overwrite existing output: {output_zip}")

    candidate_bin, candidate_cue, b319 = validate_batch319(pack_dir)
    sidecars = validate_required_sidecars(pack_dir)

    patch_sha = sha256_file(patch)
    ledger_sha = sha256_file(ledger)
    cue_sha = sha256_file(candidate_cue)

    release_manifest = {
        "batch": 320,
        "status": PASS320,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate_batch": 309,
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "changed_sectors": EXPECTED_CHANGED,
            "estimated_or_guessed_bytes": 0,
            "batch319_status": b319.get("status"),
        },
        "distribution": {
            "format": "deterministic_zip_without_full_bin",
            "fixed_zip_timestamp": "2026-08-12T00:00:00",
            "full_candidate_bin_included": False,
            "candidate_bin_name": candidate_bin.name,
            "candidate_bin_sha256": CANDIDATE_SHA256,
            "candidate_cue_name": candidate_cue.name,
            "candidate_cue_sha256": cue_sha,
            "patch_name": patch.name,
            "patch_sha256": patch_sha,
            "ledger_name": ledger.name,
            "ledger_sha256": ledger_sha,
        },
        "gates": {
            "batch319_manifest": "PASS",
            "materialized_candidate_full_sha256": "PASS",
            "batch317_physical_gate_sidecar_present": "PASS",
            "batch318_materializer_sidecar_present": "PASS",
            "batch319_cue_layout_preserved": "PASS",
            "changed_sectors": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "estimated_or_guessed_bytes": 0,
        },
        "hardware_validation": "PENDING; deterministic package does not replace SSF/real-hardware playback validation",
    }
    manifest_bytes = (json.dumps(release_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    members: list[tuple[str, Path | bytes]] = [
        (f"candidate/{candidate_cue.name}", candidate_cue),
        (f"patch/{patch.name}", patch),
        (f"ledger/{ledger.name}", ledger),
    ]
    for p in sidecars:
        members.append((f"proof/{p.name}", p))
    members.append(("proof/BATCH320_RELEASE_PACKAGE.json", manifest_bytes))
    members.sort(key=lambda x: x[0])

    sums_lines: list[str] = []
    for arcname, payload in members:
        digest = hashlib.sha256(payload).hexdigest() if isinstance(payload, bytes) else sha256_file(payload)
        sums_lines.append(f"{digest}  {arcname}\n")
    sums_lines.append(f"{CANDIDATE_SHA256}  NOT_INCLUDED/{candidate_bin.name}\n")
    sums_bytes = "".join(sums_lines).encode("utf-8")
    members.append(("SHA256SUMS_RELEASE.txt", sums_bytes))
    members.sort(key=lambda x: x[0])

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=output_zip.name + ".", suffix=".tmp", dir=output_zip.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as zf:
            for arcname, payload in members:
                if isinstance(payload, bytes):
                    zip_write_bytes(zf, payload, arcname)
                else:
                    zip_write_file(zf, payload, arcname)

        # Re-open and prove archive member names/content hashes before publish.
        with zipfile.ZipFile(tmp, "r") as zf:
            names = zf.namelist()
            expected_names = [name for name, _ in members]
            if names != expected_names:
                die("ZIP member ordering/name set mismatch")
            if len(names) != len(set(names)):
                die("ZIP contains duplicate member names")
            for arcname, payload in members:
                expected = hashlib.sha256(payload).hexdigest() if isinstance(payload, bytes) else sha256_file(payload)
                h = hashlib.sha256()
                with zf.open(arcname, "r") as f:
                    for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                        h.update(chunk)
                if h.hexdigest() != expected:
                    die(f"ZIP round-trip SHA-256 mismatch: {arcname}")

        tmp.replace(output_zip)
    finally:
        tmp.unlink(missing_ok=True)

    print(PASS320)
    print(f"release_zip={output_zip}")
    print(f"release_zip_sha256={sha256_file(output_zip)}")
    print(f"candidate_bin_sha256={CANDIDATE_SHA256} (verified, intentionally not embedded)")
    print(f"changed_sectors={EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
