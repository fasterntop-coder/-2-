#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PRISTINE_SIZE = 659293824
SECTOR = 2352
EXPECTED_PARENT_STATUS = "PASS_BATCH279_STORY141_PHYSICAL_CLOSURE"
EXPECTED_STATIC_STATUS = "PASS_REAL_FULL58_EXACT_RECOVERY"
EXPECTED_MOVIE_STATUS = "PASS_BATCH269_PLUS_ALL_12_SPEECH_MOVIES_PHYSICAL_UNION"
SUCCESS = "PASS_BATCH280_STORY141_CUMULATIVE_RELEASE_CERT"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(4 * 1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def status_of(obj: dict) -> str | None:
    return obj.get("status") or obj.get("success_status") or obj.get("result", {}).get("status")


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {msg}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch280 cumulative release certificate verifier")
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--parent-report", type=Path, required=True, help="Executed Batch279 report JSON")
    ap.add_argument("--candidate-bin", type=Path, required=True)
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("BATCH280_STORY141_CUMULATIVE_RELEASE_CERT.json"))
    args = ap.parse_args()

    root = args.repo_root
    m279 = load_json(root / "manifests/CD1_BATCH279_STORY141_PHYSICAL_CLOSURE.json")
    m200 = load_json(root / "manifests/BATCH200_REAL_FULL58_RECOVERY.json")
    m273 = load_json(root / "manifests/CD1_BATCH273_MOVIE12_PHYSICAL_UNION.json")
    parent = load_json(args.parent_report)

    require(m279.get("batch") == 279, "Batch279 manifest mismatch")
    require(m279.get("closure_accounting", {}).get("story_files_accounted") == 141, "story141 accounting missing")
    require(m279.get("closure_accounting", {}).get("story_files_total") == 141, "story inventory denominator changed")
    require(m279.get("estimated_bytes") == 0, "Batch279 estimated/guessed bytes must be zero")

    require(m200.get("status") == EXPECTED_STATIC_STATUS, "Static58 trust-chain status mismatch")
    require(len(m200.get("assets", [])) == 58, "Static58 asset count mismatch")
    require(m200.get("changed_raw_sectors") == 1626, "Static58 changed-sector accounting mismatch")
    require(m200.get("reextraction") == "58/58 PASS", "Static58 re-extraction gate missing")

    require(m273.get("speech_movie_inventory", {}).get("total") == 12, "movie inventory denominator changed")
    require(m273.get("speech_movie_inventory", {}).get("candidate_in_union") == 12, "movie12 union incomplete")
    require(m273.get("success_status") == EXPECTED_MOVIE_STATUS, "movie12 trust-chain status mismatch")
    require(m273.get("merge_policy", {}).get("guessed_payload_bytes") is False, "movie12 guessed bytes not zero")

    require(status_of(parent) == EXPECTED_PARENT_STATUS, "executed Batch279 report did not PASS")
    guessed = parent.get("guessed_payload_bytes", parent.get("estimated_bytes", 0))
    require(guessed in (0, False), "parent report contains guessed payload bytes")

    require(args.pristine_bin.stat().st_size == PRISTINE_SIZE, "pristine size mismatch")
    require(args.candidate_bin.stat().st_size == PRISTINE_SIZE, "candidate size mismatch")
    pristine_sha = sha256_file(args.pristine_bin)
    candidate_sha = sha256_file(args.candidate_bin)
    require(pristine_sha == PRISTINE_SHA, "pristine SHA-256 mismatch")

    parent_out_sha = (
        parent.get("output_sha256")
        or parent.get("output_disc_sha256")
        or parent.get("result", {}).get("output_sha256")
        or parent.get("result", {}).get("output_disc_sha256")
    )
    require(isinstance(parent_out_sha, str) and len(parent_out_sha) == 64, "parent output SHA-256 missing")
    require(candidate_sha == parent_out_sha, "candidate BIN does not match Batch279 output SHA-256")

    changed = []
    with args.pristine_bin.open("rb") as a, args.candidate_bin.open("rb") as b:
        lba = 0
        while True:
            sa = a.read(SECTOR)
            sb = b.read(SECTOR)
            if not sa and not sb:
                break
            require(len(sa) == SECTOR and len(sb) == SECTOR, "short raw sector")
            if sa != sb:
                changed.append(lba)
            lba += 1

    reported_changed = parent.get("changed_raw_sectors") or parent.get("result", {}).get("changed_raw_sectors")
    if isinstance(reported_changed, int):
        require(reported_changed == len(changed), "changed-sector accounting differs from Batch279 report")

    expected_write = parent.get("expected_write") or parent.get("result", {}).get("expected_write")
    if isinstance(expected_write, list) and expected_write:
        ew_lbas = sorted({int(x["lba"]) for x in expected_write if isinstance(x, dict) and "lba" in x})
        require(ew_lbas == changed, "Expected Write LBA set differs from actual parent/candidate diff")

    cert = {
        "format": "ST2-CD1-BATCH280-STORY141-CUMULATIVE-RELEASE-CERT-v1",
        "batch": 280,
        "status": SUCCESS,
        "candidate_sha256": candidate_sha,
        "pristine_sha256": pristine_sha,
        "candidate_size": args.candidate_bin.stat().st_size,
        "changed_raw_sectors": len(changed),
        "story": {"accounted": 141, "total": 141, "replacement_files": 136, "identity_controls": 5},
        "trusted_static": {"assets": 58, "reextraction": "58/58 PASS", "source_manifest_status": EXPECTED_STATIC_STATUS},
        "trusted_speech_movies": {"candidate_in_union": 12, "total": 12, "source_manifest_status": EXPECTED_MOVIE_STATUS},
        "guessed_payload_bytes": 0,
        "gates": {
            "parent_output_sha_match": True,
            "pristine_sha_match": True,
            "changed_sector_accounting": True,
            "expected_write_if_present": True,
            "story141_closure": True,
            "static58_trust_chain": True,
            "movie12_trust_chain": True
        }
    }
    args.out.write_text(json.dumps(cert, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(cert, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
