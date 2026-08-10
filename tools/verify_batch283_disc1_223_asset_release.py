#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import verify_mode1_sector

RAW = 2352
USER_OFF = 16
USER_SIZE = 2048
DISC_SIZE = 659293824
PRISTINE_SHA = "d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
SUCCESS = "PASS_BATCH283_DISC1_223_ASSET_RELEASE_GATE"
PARENT_STATUS = "PASS_BATCH282_STATIC58_PHYSICAL_REUNION"
B281_STATUS = "PASS_BATCH281_MOVIE24_LOGICAL_CLOSURE"
B200_STATUS = "PASS_REAL_FULL58_EXACT_RECOVERY"


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {msg}")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_asset(path: Path, lba: int, size: int) -> bytes:
    require(lba >= 0 and size > 0, "invalid asset geometry")
    out = bytearray()
    sectors = (size + USER_SIZE - 1) // USER_SIZE
    with path.open("rb") as f:
        for i in range(sectors):
            cur = lba + i
            f.seek(cur * RAW)
            sec = f.read(RAW)
            require(len(sec) == RAW, f"short sector LBA {cur}")
            require(sec[15] == 1, f"non-MODE1 sector LBA {cur}")
            out += sec[USER_OFF:USER_OFF + USER_SIZE]
    return bytes(out[:size])


def changed_lbas(a: Path, b: Path, verify_b: bool = True) -> list[int]:
    changed: list[int] = []
    with a.open("rb") as fa, b.open("rb") as fb:
        lba = 0
        while True:
            sa, sb = fa.read(RAW), fb.read(RAW)
            if not sa and not sb:
                break
            require(len(sa) == RAW and len(sb) == RAW, "short raw sector during comparison")
            if sa != sb:
                if verify_b:
                    require(verify_mode1_sector(sb).get("valid") is True,
                            f"changed candidate sector failed EDC/ECC LBA {lba}")
                changed.append(lba)
            lba += 1
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch283 cumulative Disc1 223-asset release verifier")
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--pristine-bin", type=Path, required=True)
    ap.add_argument("--parent-bin", type=Path, required=True, help="Exact B281 parent BIN used by Batch282")
    ap.add_argument("--candidate-bin", type=Path, required=True, help="Exact B282 result BIN")
    ap.add_argument("--batch282-result", type=Path, required=True)
    ap.add_argument("--batch281-cert", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("BATCH283_DISC1_223_ASSET_RELEASE_CERT.json"))
    args = ap.parse_args()

    root = args.repo_root
    m283 = load_json(root / "manifests/CD1_BATCH283_DISC1_223_ASSET_RELEASE_GATE.json")
    m279 = load_json(root / "manifests/CD1_BATCH279_STORY141_PHYSICAL_CLOSURE.json")
    m281 = load_json(root / "manifests/CD1_BATCH281_MOVIE24_LOGICAL_CLOSURE.json")
    m282 = load_json(root / "manifests/CD1_BATCH282_STATIC58_PHYSICAL_REUNION.json")
    m200 = load_json(root / "manifests/BATCH200_REAL_FULL58_RECOVERY.json")
    r282 = load_json(args.batch282_result)
    c281 = load_json(args.batch281_cert)

    require(m283.get("batch") == 283 and m283.get("estimated_bytes") == 0, "Batch283 manifest gate")
    require(m279.get("closure_accounting", {}).get("story_files_accounted") == 141, "story141 lineage")
    require(m281.get("cumulative_logical_coverage", {}).get("logical_assets_accounted") == 223,
            "Batch281 223-accounting lineage")
    require(m282.get("donor", {}).get("asset_count") == 58, "Batch282 static58 lineage")
    require(m200.get("status") == B200_STATUS, "B200 status")
    require(m200.get("reextraction") == "58/58 PASS", "B200 58/58 lineage")
    require(len(m200.get("assets", [])) == 58, "B200 asset count")
    require(c281.get("status") == B281_STATUS, "executed B281 certificate status")
    require(c281.get("guessed_payload_bytes") == 0, "B281 guessed bytes")
    require(c281.get("cumulative_logical_coverage", {}).get("logical_assets_accounted") == 223,
            "executed B281 223 accounting")
    require(r282.get("status") == PARENT_STATUS, "executed B282 result status")
    require(r282.get("guessed_payload_bytes") == 0, "B282 guessed bytes")
    require(r282.get("asset_reextraction") == "58/58 PASS", "B282 static58 reextraction status")

    for p in (args.pristine_bin, args.parent_bin, args.candidate_bin):
        require(p.stat().st_size == DISC_SIZE, f"disc size mismatch: {p}")
    pristine_sha = sha_file(args.pristine_bin)
    parent_sha = sha_file(args.parent_bin)
    candidate_sha = sha_file(args.candidate_bin)
    require(pristine_sha == PRISTINE_SHA, "pristine SHA-256")
    require(parent_sha == r282.get("parent_sha256"), "B282 parent SHA binding")
    require(candidate_sha == r282.get("output_sha256"), "B282 candidate SHA binding")
    require(parent_sha == c281.get("candidate_sha256"), "B281 certificate -> B282 parent binding")

    # Physical B281 -> B282 delta must equal the Expected Write set exactly.
    delta_lbas = changed_lbas(args.parent_bin, args.candidate_bin)
    expected = r282.get("expected_write", [])
    require(isinstance(expected, list), "B282 Expected Write list missing")
    expected_by_lba = {int(x["lba"]): x for x in expected}
    require(len(expected_by_lba) == len(expected), "duplicate B282 Expected Write LBA")
    require(sorted(expected_by_lba) == delta_lbas, "B281->B282 changed LBA != Expected Write LBA")
    require(r282.get("changed_raw_sectors") == len(delta_lbas), "B282 changed-sector accounting")

    with args.parent_bin.open("rb") as fp, args.candidate_bin.open("rb") as fc:
        for lba in delta_lbas:
            fp.seek(lba * RAW); fc.seek(lba * RAW)
            before, after = fp.read(RAW), fc.read(RAW)
            rec = expected_by_lba[lba]
            require(sha_bytes(before) == rec.get("before_sha256"), f"Expected Write before SHA LBA {lba}")
            require(sha_bytes(after) == rec.get("after_sha256"), f"Expected Write after SHA LBA {lba}")
            require(verify_mode1_sector(after).get("valid") is True, f"B282 EDC/ECC LBA {lba}")

    # Independently audit every sector that differs from pristine in the final candidate.
    final_changed = changed_lbas(args.pristine_bin, args.candidate_bin)

    # Re-extract all 58 exact battle/static assets from the final candidate.
    static_audit = []
    for a in m200["assets"]:
        name = a["name"]
        got = sha_bytes(extract_asset(args.candidate_bin, int(a["lba"]), int(a["size"])))
        require(got == a["sha256"], f"final static58 whole-asset SHA: {name}")
        static_audit.append({"asset": name, "lba": int(a["lba"]), "size": int(a["size"]),
                             "sha256": got, "status": "PASS"})

    # Re-extract all six movies which are intentionally preserved byte-identical to pristine.
    preserved = m281.get("identity_preserved_movies", [])
    require(len(preserved) == 6, "movie identity-preserved count")
    movie_audit = []
    for a in preserved:
        got = sha_bytes(extract_asset(args.candidate_bin, int(a["lba"]), int(a["size"])))
        require(got == a["source_sha256"], f"identity movie SHA: {a['iso_path']}")
        movie_audit.append({"asset": a["iso_path"], "lba": int(a["lba"]), "size": int(a["size"]),
                            "sha256": got, "status": "PASS_ORIGINAL_PRESERVED"})

    result = {
        "format": "ST2-CD1-BATCH283-DISC1-223-ASSET-RELEASE-CERT-v1",
        "batch": 283,
        "status": SUCCESS,
        "pristine_sha256": pristine_sha,
        "parent_sha256": parent_sha,
        "candidate_sha256": candidate_sha,
        "candidate_size": DISC_SIZE,
        "guessed_payload_bytes": 0,
        "batch282_delta_changed_raw_sectors": len(delta_lbas),
        "batch282_expected_write_count": len(expected),
        "final_changed_raw_sectors_from_pristine": len(final_changed),
        "final_changed_sector_edc_ecc": f"{len(final_changed)}/{len(final_changed)} PASS",
        "static58_reextraction": "58/58 PASS",
        "movie_identity_reextraction": "6/6 PASS",
        "static58_audit": static_audit,
        "movie_identity_audit": movie_audit,
        "cumulative_scope": {
            "story": "141/141 trust-chain sealed",
            "battle_static": "58/58 final whole-asset reextracted",
            "movie_static_inventory": "24/24 logical; six identity movies final reextracted",
            "logical_assets_accounted": 223,
            "logical_assets_total": 223
        },
        "gates": {
            "pristine_sha_binding": True,
            "b281_certificate_binding": True,
            "b282_parent_output_sha_binding": True,
            "expected_write_exact_delta": True,
            "changed_sector_accounting": True,
            "batch282_delta_edc_ecc": True,
            "final_all_changed_sectors_edc_ecc": True,
            "story141_trust_chain": True,
            "static58_final_reextraction": True,
            "movie6_identity_final_reextraction": True,
            "guessed_bytes_zero": True
        }
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(SUCCESS)
    print(f"candidate_sha256={candidate_sha}")
    print(f"logical_assets=223/223")
    print(f"static58=58/58 movie_identity=6/6 final_changed_sectors={len(final_changed)}")


if __name__ == "__main__":
    main()
