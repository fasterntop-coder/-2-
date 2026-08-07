#!/usr/bin/env python3
import json, sys
from pathlib import Path

EXPECTED = {
  "SYS33": "dd7ae13f8d3040e64f45bda4c8ff4decbd26be009ea3fc705bf30a52a7c39952",
  "SYS27": "9395944d4333ff570315b105e6989070cb7cf3eee30854cb2c6e78fb778605ce",
  "SYS31": "2e38e13d50d2f9e0ac2daa810088f9e25b0023214dd0c59372b42c9170e05e89",
  "SYS34": "26cac2ce38de1b44448fadc04d4181e188e40a496883cc142a7a7a44603d7ef1",
  "SYS04": "e96b7eaf90a0bad9176e1f5b930c51106cef566aaf00b67119477ac66d7092d3",
  "SYS29": "dd51615e7e9fc02c17ac6e232e4860c3989f7e00fc063f6978c9881acc49e44f",
}

def die(msg):
    raise SystemExit(f"FAIL: {msg}")

def main(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    base = data.get("baseline", {})
    if base.get("previous_exact_assets") != 45: die("previous exact asset count")
    if base.get("exact_assets") != 51 or base.get("total_static_assets") != 58: die("51/58 geometry")
    if set(base.get("added_assets", [])) != set(EXPECTED): die("added asset set")
    ev = data.get("batch112_evidence", {})
    if ev.get("records") != 1374: die("record count")
    if ev.get("lba_conflicts") != 0: die("LBA conflict")
    if ev.get("edc_ecc") != "PASS": die("EDC/ECC")
    if ev.get("reextraction") != "13/13 PASS": die("re-extraction")
    if ev.get("candidate_sha256") != EXPECTED: die("candidate hashes")
    policy = data.get("overall_progress_policy", {})
    if float(policy.get("official_runtime_implementation_percent", -1)) >= 70.0:
        die("overall 70 percent may not be claimed without a unified validated Disc candidate")
    if data.get("estimated_bytes") != 0: die("estimated bytes forbidden")
    print("PASS_EXACT51_BASELINE_OVERALL_70_GATE")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_cd1_exact51_and_overall_gate.py manifest.json")
    main(sys.argv[1])
