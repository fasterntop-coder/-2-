#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "manifests" / "CD1_INTEGRATION_READINESS_BATCH230.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload-dir", type=Path, help="Directory containing exact replacement bodies by basename")
    ap.add_argument("--check-readiness-only", action="store_true")
    args = ap.parse_args()

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["policy"]["no_speculative_bytes"] is True
    assert data["static58"]["assets"] == "58/58"
    assert data["static58"]["records"] == "12595/12595"
    assert data["static58"]["lba_conflicts"] == 0
    assert data["static58"]["other_changed_sectors"] == 0
    assert data["static58"]["edc_ecc"] == "PASS"
    assert data["static58"]["reextraction"] == "58/58 PASS"
    assert data["story_source_inventory"]["unprocessed_candidate_records"] == 0
    assert data["movie_static_inventory"]["inventory"] == "24/24"

    expected = {}
    expected.update(data["story_large_bin_known_replacements"])
    expected.update(data["story_source_inventory"]["batch62_replacement_hashes"])

    if args.check_readiness_only or args.payload_dir is None:
        print("PASS_READINESS_METADATA")
        print("MASTER_WRITE_BLOCKED_UNTIL_EXACT_PAYLOAD_BODIES_PRESENT")
        return 0

    missing = []
    bad = []
    for iso_path, digest in expected.items():
        p = args.payload_dir / Path(iso_path).name
        if not p.is_file():
            missing.append(str(p))
            continue
        got = sha256_file(p)
        if got != digest:
            bad.append((str(p), digest, got))

    if missing or bad:
        for p in missing:
            print(f"MISSING {p}")
        for p, exp, got in bad:
            print(f"SHA_MISMATCH {p} expected={exp} got={got}")
        print("FAIL_PAYLOAD_GATE")
        return 2

    print(f"PASS_EXACT_PAYLOAD_SHA_GATE {len(expected)}/{len(expected)}")
    print("NEXT_REQUIRED_GATE=EXPECTED_WRITE_LBA_EDC_ECC_REEXTRACTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
