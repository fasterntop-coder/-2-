#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "manifests" / "CD1_STATIC58_BASELINE_BATCH229.json"
EXPECTED_FOUNDATION = {
    "PBOOK_BT": "4376a5c2a59639041793a56cccebe25256b26ef7b4db5d3bad81c2b12d184bfe",
    "PBOOK_EC": "378d92a4daf3db00d7c172ae8d233fad1fe3e1452cb979e9bd8b5610220152f5",
    "PBOOK_RC": "c5bc0866ea5581f64bccb0a9da1c6baf53c77601fa247469441e49d0eaae4907",
    "SYS00": "d77e54e7b7d2f8a094e2855a199ec33f43ecf5802f139c1d84df3f0de75bc98a",
    "SYS01": "c2bc383d96a9ccfd0c844f28363b6af15063921d42bb9142cf6b8edb4cbf7101",
    "SYS26": "fd01d17f820cfad7a006e9b1ebc35ad618badbfc948a11fefe116438f3db6021",
    "STNSYS00": "92583409bb2f70f19795180e341756d1ad81603138893bf3f270b5f113ce37ad",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def main() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if m["previous_baseline"]["assets"] != 51:
        return fail("previous baseline is not exact51")
    if len(m["added_foundation_assets"]) != 7:
        return fail("foundation asset count != 7")
    names = [a["asset"] for a in m["added_foundation_assets"]]
    if set(names) != set(EXPECTED_FOUNDATION):
        return fail("foundation asset set mismatch")
    for a in m["added_foundation_assets"]:
        if a["candidate_sha256"] != EXPECTED_FOUNDATION[a["asset"]]:
            return fail(f"candidate SHA mismatch: {a['asset']}")
    ev = m["batch118_full_disc_evidence"]
    required = {
        "assets": 58,
        "battle_banks": "55/55",
        "battle_static_records": "12595/12595",
        "changed_sectors": 1626,
        "lba_conflicts": 0,
        "other_changed_sectors": 0,
        "mode1_2352_edc_ecc": "PASS",
        "reextraction": "58/58 PASS",
        "verification_output_bin_sha256": "75f300e59bd3ad63ca11d4981f328107aa59397fa894abbf5d02476a6457df20",
    }
    for k, v in required.items():
        if ev.get(k) != v:
            return fail(f"Batch118 evidence mismatch for {k}: {ev.get(k)!r}")
    if m["result"]["estimated_bytes_applied"] != 0:
        return fail("estimated bytes were applied")
    if m["result"]["static_assets"] != "58/58":
        return fail("static 58/58 gate not closed")

    # Optional byte proof: pass a directory containing any subset of the seven
    # foundation assets. Supplied files must match their exact candidate SHA.
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
        checked = 0
        for name, expected in EXPECTED_FOUNDATION.items():
            candidates = [root / name, root / f"{name}.MES", root / f"{name}.CG"]
            p = next((x for x in candidates if x.is_file()), None)
            if p is None:
                continue
            got = sha256(p)
            if got != expected:
                return fail(f"byte proof SHA mismatch: {p} {got}")
            checked += 1
        print(f"OPTIONAL_BYTE_PROOF_PASS={checked}")

    print("PASS_CD1_STATIC58_BATCH229")
    print("STATIC_ASSETS=58/58")
    print("BATTLE_BANKS=55/55")
    print("EDC_ECC=PASS")
    print("REEXTRACTION=58/58 PASS")
    print("ESTIMATED_BYTES=0")
    print("OVERALL_CD1_RUNTIME_IMPLEMENTATION=46.3%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
