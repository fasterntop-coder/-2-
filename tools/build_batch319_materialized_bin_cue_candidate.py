#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PRISTINE_SHA256 = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256 = "8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_CHANGED = 90_272
PASS318 = "PASS_B318_MATERIALIZED_CD1_CANDIDATE"
PASS319 = "PASS_B319_MATERIALIZED_BIN_CUE_CANDIDATE_PACK"
DEFAULT_BIN_NAME = "Sakura_Taisen_2_Disc1_KR_Batch309_Physical.bin"
DEFAULT_CUE_NAME = "Sakura_Taisen_2_Disc1_KR_Batch319.cue"
FILE_RE = re.compile(r'^(?P<prefix>\s*FILE\s+)(?P<name>"[^"]+"|\S+)(?P<suffix>\s+\S+.*)$', re.IGNORECASE)


def die(msg: str) -> None:
    raise SystemExit("FAIL " + msg)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_checked(cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
    cp = subprocess.run(cmd, text=True, capture_output=True)
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout).strip()
        die(f"{label} failed: {detail}")
    return cp


def cue_file_tokens(text: str) -> list[tuple[int, re.Match[str]]]:
    out: list[tuple[int, re.Match[str]]] = []
    for idx, line in enumerate(text.splitlines()):
        m = FILE_RE.match(line)
        if m:
            out.append((idx, m))
    return out


def unquote(token: str) -> str:
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return token[1:-1]
    return token


def rewrite_cue_exact(source_text: str, pristine_bin: Path, candidate_bin_name: str) -> tuple[str, dict[str, object]]:
    lines = source_text.splitlines(keepends=True)
    logical = source_text.splitlines()
    matches = cue_file_tokens(source_text)
    if not matches:
        die("source CUE has no FILE directive")

    pristine_name = pristine_bin.name.casefold()
    exact_name_matches: list[int] = []
    bin_directives: list[int] = []
    for line_idx, m in matches:
        token_name = Path(unquote(m.group("name"))).name
        suffix_upper = m.group("suffix").upper()
        if token_name.casefold() == pristine_name:
            exact_name_matches.append(line_idx)
        if "BINARY" in suffix_upper or token_name.lower().endswith(".bin"):
            bin_directives.append(line_idx)

    if len(exact_name_matches) == 1:
        target_idx = exact_name_matches[0]
        selection = "EXACT_PRISTINE_BASENAME"
    elif len(matches) == 1:
        target_idx = matches[0][0]
        selection = "ONLY_FILE_DIRECTIVE"
    elif len(bin_directives) == 1:
        target_idx = bin_directives[0]
        selection = "ONLY_BINARY_OR_BIN_DIRECTIVE"
    else:
        die(
            "source CUE target FILE directive is ambiguous; exact pristine basename did not uniquely identify it"
        )

    old_line = logical[target_idx]
    m = FILE_RE.match(old_line)
    if not m:
        die("internal CUE FILE parsing error")
    old_token = m.group("name")
    quote = old_token.startswith('"') and old_token.endswith('"')
    new_token = f'"{candidate_bin_name}"' if quote or " " in candidate_bin_name else candidate_bin_name
    new_line_no_eol = f'{m.group("prefix")}{new_token}{m.group("suffix")}'

    original_physical = lines[target_idx]
    if original_physical.endswith("\r\n"):
        eol = "\r\n"
    elif original_physical.endswith("\n"):
        eol = "\n"
    elif original_physical.endswith("\r"):
        eol = "\r"
    else:
        eol = ""
    lines[target_idx] = new_line_no_eol + eol
    rewritten = "".join(lines)

    # Prove that only the selected FILE token changed; all other bytes/lines are preserved by construction.
    before_normalized = list(logical)
    after_normalized = rewritten.splitlines()
    if len(before_normalized) != len(after_normalized):
        die("CUE rewrite changed line count")
    changed_lines = [i for i, (a, b) in enumerate(zip(before_normalized, after_normalized)) if a != b]
    if changed_lines != [target_idx]:
        die(f"CUE rewrite touched unexpected lines: {changed_lines}")

    return rewritten, {
        "selection": selection,
        "target_line_1based": target_idx + 1,
        "source_file_token": unquote(old_token),
        "candidate_file_token": candidate_bin_name,
        "file_directive_count": len(matches),
        "changed_cue_lines": 1,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Batch319: build an executable Disc 1 BIN/CUE candidate pack by invoking the exact Batch318 "
            "materializer, then rewrite only the source CUE FILE token that points at the data BIN. "
            "Track/index layout is preserved byte-for-byte outside that one FILE line; no guessed layout is emitted."
        )
    )
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--source-cue", type=Path, required=True)
    ap.add_argument("--patch-file", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--output-bin-name", default=DEFAULT_BIN_NAME)
    ap.add_argument("--output-cue-name", default=DEFAULT_CUE_NAME)
    args = ap.parse_args()

    root = args.repo_root.resolve()
    pristine = args.pristine_bin.resolve()
    source_cue = args.source_cue.resolve()
    patch = args.patch_file.resolve()
    ledger = args.ledger.resolve()
    outdir = args.output_dir.resolve()

    for p, label in (
        (pristine, "pristine BIN"),
        (source_cue, "source CUE"),
        (patch, "Batch314 sparse patch"),
        (ledger, "Batch316 ledger"),
    ):
        if not p.is_file():
            die(f"missing {label}: {p}")
    if sha256_file(pristine) != PRISTINE_SHA256:
        die("pristine Disc 1 SHA-256 mismatch")

    builder318 = root / "tools" / "build_batch318_materialized_cd1_candidate.py"
    if not builder318.is_file():
        die(f"missing Batch318 materializer: {builder318}")

    outdir.mkdir(parents=True, exist_ok=True)
    final_bin = outdir / args.output_bin_name
    final_cue = outdir / args.output_cue_name
    manifest_path = outdir / "BATCH319_MATERIALIZED_BIN_CUE_CANDIDATE.json"
    sums_path = outdir / "SHA256SUMS.txt"
    for p in (final_bin, final_cue, manifest_path, sums_path):
        if p.exists():
            die(f"refusing to overwrite existing output: {p}")

    source_cue_bytes = source_cue.read_bytes()
    try:
        source_cue_text = source_cue_bytes.decode("utf-8-sig")
        cue_encoding = "utf-8-sig"
    except UnicodeDecodeError:
        try:
            source_cue_text = source_cue_bytes.decode("cp932")
            cue_encoding = "cp932"
        except UnicodeDecodeError as exc:
            die(f"source CUE is neither UTF-8 nor CP932 decodable: {exc}")

    rewritten_cue_text, cue_rewrite = rewrite_cue_exact(source_cue_text, pristine, final_bin.name)

    with tempfile.TemporaryDirectory(prefix="st2_b319_") as td:
        stage = Path(td) / "b318"
        run_checked(
            [
                sys.executable,
                str(builder318),
                "--repo-root", str(root),
                "--pristine-bin", str(pristine),
                "--patch-file", str(patch),
                "--ledger", str(ledger),
                "--output-dir", str(stage),
                "--output-bin-name", final_bin.name,
            ],
            "Batch318 exact materializer",
        )
        staged_bin = stage / final_bin.name
        staged_manifest = stage / "BATCH318_MATERIALIZED_CD1_CANDIDATE.json"
        staged_gate = stage / "BATCH317_PHYSICAL_GATE.json"
        if not staged_bin.is_file() or not staged_manifest.is_file() or not staged_gate.is_file():
            die("Batch318 output set is incomplete")
        b318 = json.loads(staged_manifest.read_text(encoding="utf-8"))
        if b318.get("status") != PASS318:
            die("Batch318 status mismatch")
        if b318.get("output", {}).get("changed_sectors_applied") != EXPECTED_CHANGED:
            die("Batch318 changed-sector count mismatch")
        if sha256_file(staged_bin) != CANDIDATE_SHA256:
            die("Batch318 staged BIN SHA-256 mismatch")

        shutil.copyfile(staged_bin, final_bin)
        shutil.copyfile(staged_manifest, outdir / staged_manifest.name)
        shutil.copyfile(staged_gate, outdir / staged_gate.name)

    if sha256_file(final_bin) != CANDIDATE_SHA256:
        final_bin.unlink(missing_ok=True)
        die("final copied BIN SHA-256 mismatch")

    # Emit CUE using the source encoding to avoid needless textual churn.
    if cue_encoding == "cp932":
        final_cue.write_bytes(rewritten_cue_text.encode("cp932"))
    else:
        # UTF-8 BOM is not semantically required; preserve BOM only if the source had one.
        if source_cue_bytes.startswith(b"\xef\xbb\xbf"):
            final_cue.write_bytes(b"\xef\xbb\xbf" + rewritten_cue_text.encode("utf-8"))
        else:
            final_cue.write_text(rewritten_cue_text, encoding="utf-8", newline="")

    # Reparse emitted CUE and prove it now points at the materialized candidate BIN.
    emitted_bytes = final_cue.read_bytes()
    if cue_encoding == "cp932":
        emitted_text = emitted_bytes.decode("cp932")
    else:
        emitted_text = emitted_bytes.decode("utf-8-sig")
    emitted_tokens = [Path(unquote(m.group("name"))).name for _, m in cue_file_tokens(emitted_text)]
    if final_bin.name not in emitted_tokens:
        die("emitted CUE does not reference the materialized candidate BIN")

    manifest = {
        "batch": 319,
        "status": PASS319,
        "goal": "CD1_100_PERCENT_CANDIDATE",
        "authoritative_candidate_batch": 309,
        "materialized_by": {
            "sparse_patch_batch": 314,
            "canonical_ledger_batch": 316,
            "physical_gate_batch": 317,
            "bin_materializer_batch": 318,
            "bin_cue_pack_batch": 319,
        },
        "lineage": {
            "pristine_sha256": PRISTINE_SHA256,
            "candidate_sha256": CANDIDATE_SHA256,
            "changed_sectors": EXPECTED_CHANGED,
            "estimated_or_guessed_bytes": 0,
            "guessed_cue_layout": False,
        },
        "source_cue": {
            "name": source_cue.name,
            "sha256": hashlib.sha256(source_cue_bytes).hexdigest(),
            "encoding": cue_encoding,
        },
        "cue_rewrite": cue_rewrite,
        "output": {
            "bin": final_bin.name,
            "bin_sha256": sha256_file(final_bin),
            "cue": final_cue.name,
            "cue_sha256": sha256_file(final_cue),
        },
        "gates": {
            "batch318_materialization": "PASS",
            "batch318_changed_sectors": f"{EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS",
            "candidate_full_bin_sha256": "PASS",
            "source_cue_track_layout_preserved": "PASS",
            "cue_file_reference_retargeted": "PASS",
            "estimated_or_guessed_bytes": 0,
        },
        "hardware_validation": "PENDING; BIN/CUE candidate pack is byte-exact but playback validation remains separate",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    files_for_sums = [
        final_bin,
        final_cue,
        outdir / "BATCH317_PHYSICAL_GATE.json",
        outdir / "BATCH318_MATERIALIZED_CD1_CANDIDATE.json",
        manifest_path,
    ]
    sums_path.write_text(
        "".join(f"{sha256_file(p)}  {p.name}\n" for p in files_for_sums),
        encoding="utf-8",
    )

    print(PASS319)
    print(f"candidate_bin={final_bin}")
    print(f"candidate_cue={final_cue}")
    print(f"changed_sectors={EXPECTED_CHANGED}/{EXPECTED_CHANGED} PASS")
    print(f"candidate_sha256={CANDIDATE_SHA256}")
    print("cue_track_layout_preserved=PASS")
    print("estimated_or_guessed_bytes=0")


if __name__ == "__main__":
    main()
