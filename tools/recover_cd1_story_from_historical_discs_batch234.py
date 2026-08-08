#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from mode1_2352 import RAW_SECTOR_SIZE, verify_mode1_sector

USER_OFFSET = 16
USER_SIZE = 2048
DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "manifests" / "CD1_STORY_REBUILD_INPUTS_BATCH232.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_extent(raw_disc: Path, lba: int, size: int) -> tuple[bytes, dict]:
    out = bytearray()
    sector_reports = []
    remaining = size
    sector_index = lba
    with raw_disc.open("rb") as f:
        while remaining:
            f.seek(sector_index * RAW_SECTOR_SIZE)
            raw = f.read(RAW_SECTOR_SIZE)
            if len(raw) != RAW_SECTOR_SIZE:
                raise ValueError(f"short raw sector at LBA {sector_index}")
            check = verify_mode1_sector(raw)
            sector_reports.append({"lba": sector_index, **check})
            if not check["valid"]:
                failed = [k for k, v in check.items() if k != "valid" and not v]
                raise ValueError(f"LBA {sector_index} failed MODE1 EDC/ECC: {','.join(failed)}")
            take = min(USER_SIZE, remaining)
            out.extend(raw[USER_OFFSET:USER_OFFSET + take])
            remaining -= take
            sector_index += 1
    return bytes(out), {
        "first_lba": lba,
        "sector_count": len(sector_reports),
        "all_mode1_edc_ecc_valid": all(r["valid"] for r in sector_reports),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Batch234 recover six exact CD1 story payloads from historical MODE1/2352 disc images"
    )
    ap.add_argument("root", type=Path, help="folder containing historical raw .bin disc images")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=Path("BATCH234_RECOVERED"))
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    targets = manifest["targets"]
    args.out.mkdir(parents=True, exist_ok=True)

    recovered: dict[str, dict] = {}
    inspected = []
    errors = []

    raw_bins = sorted(p for p in args.root.rglob("*.bin") if p.is_file())
    for disc in raw_bins:
        disc_result = {"path": str(disc), "size": disc.stat().st_size, "targets": []}
        if disc.stat().st_size % RAW_SECTOR_SIZE != 0:
            disc_result["classification"] = "NOT_RAW_2352_MULTIPLE"
            inspected.append(disc_result)
            continue

        any_exact = False
        for target in targets:
            try:
                data, geometry = extract_extent(disc, int(target["lba"]), int(target["size"]))
                h = sha256_bytes(data)
                if h == target["compiled_sha256"]:
                    classification = "EXACT_COMPILED_TARGET"
                    any_exact = True
                    if target["name"] not in recovered:
                        dst = args.out / target["name"]
                        dst.write_bytes(data)
                        recovered[target["name"]] = {
                            "name": target["name"],
                            "iso_path": target["iso_path"],
                            "source_disc": str(disc),
                            "lba": target["lba"],
                            "size": len(data),
                            "sha256": h,
                            "expected_sha256": target["compiled_sha256"],
                            "mode1_edc_ecc": "PASS",
                        }
                elif h == target["source_sha256"]:
                    classification = "PRISTINE_SOURCE"
                else:
                    classification = "OTHER_HISTORICAL_VARIANT"
                disc_result["targets"].append({
                    "name": target["name"],
                    "sha256": h,
                    "classification": classification,
                    **geometry,
                })
            except Exception as exc:
                errors.append({"disc": str(disc), "target": target["name"], "error": str(exc)})
                disc_result["targets"].append({
                    "name": target["name"],
                    "classification": "READ_OR_EDC_ECC_ERROR",
                    "error": str(exc),
                })
        disc_result["classification"] = "CONTAINS_EXACT_TARGET" if any_exact else "NO_EXACT_TARGET"
        inspected.append(disc_result)

    missing = [
        {
            "name": t["name"],
            "lba": t["lba"],
            "size": t["size"],
            "compiled_sha256": t["compiled_sha256"],
        }
        for t in targets if t["name"] not in recovered
    ]

    result = {
        "batch": 234,
        "status": "PASS_ALL_SIX_RECOVERED" if not missing else ("PARTIAL_RECOVERY" if recovered else "NO_EXACT_PAYLOAD_RECOVERED"),
        "policy": {
            "speculative_bytes": False,
            "acceptance": "full payload SHA-256 exact match only",
            "sector_gate": "MODE1/2352 EDC+ECC must pass on every source sector",
            "disc_write": False,
            "next_gate_after_all_six": ["Expected Write", "LBA collision", "MODE1 EDC/ECC", "re-extraction SHA-256"],
        },
        "recovered": list(recovered.values()),
        "missing": missing,
        "inspected_discs": inspected,
        "errors": errors,
    }
    (args.out / "BATCH234_RECOVERY_RESULT.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
