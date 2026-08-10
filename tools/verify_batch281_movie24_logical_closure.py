#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import verify_mode1_sector

PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
PRISTINE_SIZE = 659293824
RAW = 2352
USER_OFFSET = 16
USER_SIZE = 2048
EXPECTED_PARENT_STATUS = "PASS_BATCH280_STORY141_CUMULATIVE_RELEASE_CERT"
EXPECTED_MOVIE12_STATUS = "PASS_BATCH269_PLUS_ALL_12_SPEECH_MOVIES_PHYSICAL_UNION"
SUCCESS = "PASS_BATCH281_MOVIE24_LOGICAL_CLOSURE"


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {msg}")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def status_of(obj: dict) -> str | None:
    return obj.get("status") or obj.get("success_status") or obj.get("result", {}).get("status")


def extract_mode1_asset(bin_path: Path, lba: int, size: int) -> bytes:
    require(lba >= 0 and size >= 0, "invalid asset geometry")
    sectors = (size + USER_SIZE - 1) // USER_SIZE
    out = bytearray()
    with bin_path.open("rb") as f:
        for i in range(sectors):
            raw_lba = lba + i
            f.seek(raw_lba * RAW)
            sector = f.read(RAW)
            require(len(sector) == RAW, f"short sector while extracting LBA {raw_lba}")
            require(sector[15] == 1, f"asset sector LBA {raw_lba} is not MODE1")
            out.extend(sector[USER_OFFSET:USER_OFFSET + USER_SIZE])
    return bytes(out[:size])


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch281 Disc1 movie24 logical-closure verifier")
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--batch280-cert", type=Path, required=True, help="Executed Batch280 certificate JSON")
    ap.add_argument("--candidate-bin", type=Path, required=True, help="Exact candidate BIN certified by Batch280")
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("BATCH281_MOVIE24_LOGICAL_CLOSURE_CERT.json"))
    args = ap.parse_args()

    root = args.repo_root
    m281 = load_json(root / "manifests/CD1_BATCH281_MOVIE24_LOGICAL_CLOSURE.json")
    m280 = load_json(root / "manifests/CD1_BATCH280_STORY141_CUMULATIVE_RELEASE_CERT.json")
    m273 = load_json(root / "manifests/CD1_BATCH273_MOVIE12_PHYSICAL_UNION.json")
    cert280 = load_json(args.batch280_cert)

    require(m281.get("batch") == 281, "Batch281 manifest mismatch")
    require(m281.get("estimated_bytes") == 0, "Batch281 estimated bytes must be zero")
    require(m280.get("batch") == 280, "Batch280 manifest mismatch")
    require(status_of(cert280) == EXPECTED_PARENT_STATUS, "executed Batch280 certificate did not PASS")
    require(cert280.get("guessed_payload_bytes") == 0, "Batch280 certificate contains guessed bytes")

    cov = m281.get("cumulative_logical_coverage", {})
    require(cov.get("story") == 141, "story denominator changed")
    require(cov.get("static_verified") == 58, "static denominator changed")
    require(cov.get("movie_static_inventory") == 24, "movie denominator changed")
    require(cov.get("logical_assets_accounted") == 223, "logical coverage accounting mismatch")

    inv = m281.get("movie_static_inventory", {})
    require(inv.get("total") == 24, "movie inventory total mismatch")
    require(inv.get("speech_candidate") == 12, "speech movie count mismatch")
    require(inv.get("episode_title_card_candidate") == 6, "title-card count mismatch")
    require(inv.get("no_dialogue_original_preserved") == 6, "no-dialogue count mismatch")
    require(inv.get("localized_or_candidate") == 18, "localized movie accounting mismatch")
    require(inv.get("identity_preserved") == 6, "identity movie accounting mismatch")

    movie12 = m273.get("speech_movie_inventory", {})
    require(movie12.get("total") == 12 and movie12.get("candidate_in_union") == 12, "Batch273 movie12 union incomplete")
    require(m273.get("success_status") == EXPECTED_MOVIE12_STATUS, "Batch273 trust-chain status mismatch")
    require(m273.get("merge_policy", {}).get("guessed_payload_bytes") is False, "Batch273 guessed bytes not zero")

    expected_title_cards = set(m281.get("required_title_cards", []))
    inherited_title_cards = set(m273.get("inherited_from_batch269", {}).get("episode_title_cards", []))
    require(len(expected_title_cards) == 6, "Batch281 title-card set must contain six files")
    require(expected_title_cards == inherited_title_cards, "Batch273 title-card inheritance differs from Batch281 closure set")

    preserved = m281.get("identity_preserved_movies", [])
    require(len(preserved) == 6, "identity-preserved movie list must contain six files")
    require(len({x["iso_path"] for x in preserved}) == 6, "duplicate identity-preserved movie path")
    require(len({int(x["lba"]) for x in preserved}) == 6, "duplicate identity-preserved movie LBA")
    for item in preserved:
        require(len(item.get("source_sha256", "")) == 64, f"missing exact source SHA for {item.get('iso_path')}")
        require(int(item.get("size", 0)) > 0, f"invalid size for {item.get('iso_path')}")

    require(args.pristine_bin.stat().st_size == PRISTINE_SIZE, "pristine size mismatch")
    require(args.candidate_bin.stat().st_size == PRISTINE_SIZE, "candidate size mismatch")
    pristine_sha = sha256_file(args.pristine_bin)
    candidate_sha = sha256_file(args.candidate_bin)
    require(pristine_sha == PRISTINE_SHA, "pristine SHA-256 mismatch")
    require(candidate_sha == cert280.get("candidate_sha256"), "candidate BIN differs from Batch280 certified SHA-256")

    gates280 = cert280.get("gates", {})
    for gate in (
        "parent_output_sha_match",
        "pristine_sha_match",
        "changed_sector_accounting",
        "expected_write_if_present",
        "story141_closure",
        "static58_trust_chain",
        "movie12_trust_chain",
    ):
        require(gates280.get(gate) is True, f"Batch280 gate not sealed: {gate}")

    changed_lbas: list[int] = []
    edc_ecc_checked = 0
    with args.pristine_bin.open("rb") as pristine, args.candidate_bin.open("rb") as candidate:
        lba = 0
        while True:
            a = pristine.read(RAW)
            b = candidate.read(RAW)
            if not a and not b:
                break
            require(len(a) == RAW and len(b) == RAW, "short raw sector")
            if a != b:
                changed_lbas.append(lba)
                mode1 = verify_mode1_sector(b)
                require(mode1.get("valid") is True, f"changed sector LBA {lba} failed MODE1 EDC/ECC")
                edc_ecc_checked += 1
            lba += 1

    reported_changed = cert280.get("changed_raw_sectors")
    require(isinstance(reported_changed, int), "Batch280 changed-sector count missing")
    require(reported_changed == len(changed_lbas), "actual changed-sector accounting differs from Batch280 certificate")
    require(edc_ecc_checked == len(changed_lbas), "not every changed sector passed EDC/ECC")

    reextraction = []
    for item in preserved:
        path = item["iso_path"]
        data = extract_mode1_asset(args.candidate_bin, int(item["lba"]), int(item["size"]))
        got = hashlib.sha256(data).hexdigest()
        expected = item["source_sha256"]
        require(got == expected, f"identity-preserved whole-asset SHA mismatch: {path}")
        reextraction.append({
            "iso_path": path,
            "lba": int(item["lba"]),
            "size": int(item["size"]),
            "sha256": got,
            "status": "PASS_ORIGINAL_PRESERVED"
        })

    result = {
        "format": "ST2-CD1-BATCH281-MOVIE24-LOGICAL-CLOSURE-CERT-v1",
        "batch": 281,
        "status": SUCCESS,
        "candidate_sha256": candidate_sha,
        "pristine_sha256": pristine_sha,
        "candidate_size": args.candidate_bin.stat().st_size,
        "changed_raw_sectors": len(changed_lbas),
        "changed_sector_edc_ecc": f"{edc_ecc_checked}/{len(changed_lbas)} PASS",
        "movie_static_inventory": {
            "accounted": 24,
            "total": 24,
            "speech_candidates_trusted": 12,
            "title_card_candidates_trusted": 6,
            "no_dialogue_original_preserved_reextracted": 6
        },
        "identity_preserved_reextraction": reextraction,
        "identity_preserved_reextraction_status": "6/6 PASS",
        "cumulative_logical_coverage": {
            "story": 141,
            "static_verified": 58,
            "movie_static_inventory": 24,
            "logical_assets_accounted": 223
        },
        "guessed_payload_bytes": 0,
        "gates": {
            "batch280_parent_certificate": True,
            "candidate_sha_binding": True,
            "pristine_sha_binding": True,
            "expected_write_chain": True,
            "changed_sector_accounting": True,
            "changed_sector_edc_ecc": True,
            "movie12_trust_chain": True,
            "title_card6_inheritance": True,
            "identity_preserved_movie_reextraction_6_of_6": True,
            "movie24_inventory_closure": True
        }
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
