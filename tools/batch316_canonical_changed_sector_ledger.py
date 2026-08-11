#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct, zlib
from pathlib import Path

SECTOR=2352
MAGIC=b"ST2SP314"
VERSION=1
HEADER_FMT=">8sIIQI32s32s"
HEADER_SIZE=struct.calcsize(HEADER_FMT)
PRISTINE_SHA256="d6dba9f9217f0841b660263ac1d7894fc31a40cd854424a1dd4a6dfecda95106"
CANDIDATE_SHA256="8fe316ea3c8f5b8128f5a34908fd982534d21b84a613f1e009080092f58bfc01"
EXPECTED_FILE_SIZE=659_293_824
EXPECTED_CHANGED=90_272
PASS="PASS_B316_CANONICAL_CHANGED_SECTOR_LEDGER"

def die(msg:str)->None: raise SystemExit("FAIL "+msg)
def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(8*1024*1024),b""): h.update(c)
    return h.hexdigest()

def main()->None:
    ap=argparse.ArgumentParser(description="Batch316 canonical ledger materializer for Batch314 ST2SP314 sparse patches")
    ap.add_argument("--patch-file",type=Path,required=True)
    ap.add_argument("--ledger",type=Path,required=True)
    ap.add_argument("--summary",type=Path,required=True)
    args=ap.parse_args()
    patch=args.patch_file.resolve()
    if not patch.is_file(): die(f"missing patch: {patch}")
    patch_sha=sha256_file(patch)
    args.ledger.parent.mkdir(parents=True,exist_ok=True)
    args.summary.parent.mkdir(parents=True,exist_ok=True)
    chain=hashlib.sha256(); sector_set_chain=hashlib.sha256(); decoded_chain=hashlib.sha256()
    count=0; compressed_total=0; first=None; last=None; previous=-1
    with patch.open("rb") as f, args.ledger.open("w",encoding="utf-8",newline="\n") as out:
        hdr=f.read(HEADER_SIZE)
        if len(hdr)!=HEADER_SIZE: die("truncated header")
        magic,version,sector_size,file_size,expected_count,pristine,candidate=struct.unpack(HEADER_FMT,hdr)
        if magic!=MAGIC or version!=VERSION: die("format mismatch")
        if sector_size!=SECTOR or file_size!=EXPECTED_FILE_SIZE: die("disc geometry mismatch")
        if expected_count!=EXPECTED_CHANGED: die(f"changed-sector count {expected_count} != {EXPECTED_CHANGED}")
        if pristine.hex()!=PRISTINE_SHA256 or candidate.hex()!=CANDIDATE_SHA256: die("SHA lineage mismatch")
        for ordinal in range(expected_count):
            rec=f.read(8)
            if len(rec)!=8: die(f"truncated record {ordinal}")
            lba,clen=struct.unpack(">II",rec)
            if lba<=previous: die(f"non-increasing or duplicate LBA {lba}")
            if lba*SECTOR>=EXPECTED_FILE_SIZE: die(f"LBA outside Disc 1: {lba}")
            if clen<=0 or clen>8192: die(f"invalid compressed length at LBA {lba}")
            payload=f.read(clen)
            if len(payload)!=clen: die(f"truncated payload at LBA {lba}")
            try: raw=zlib.decompress(payload)
            except zlib.error as e: die(f"zlib error at LBA {lba}: {e}")
            if len(raw)!=SECTOR: die(f"decoded sector size at LBA {lba}: {len(raw)}")
            psha=hashlib.sha256(payload).hexdigest(); ssha=hashlib.sha256(raw).hexdigest()
            row={"ordinal":ordinal,"lba":lba,"raw_offset":lba*SECTOR,"compressed_bytes":clen,"compressed_sha256":psha,"candidate_sector_sha256":ssha}
            line=json.dumps(row,sort_keys=True,separators=(",",":")); out.write(line+"\n")
            chain.update((line+"\n").encode()); sector_set_chain.update(struct.pack(">I",lba)); decoded_chain.update(bytes.fromhex(ssha))
            compressed_total+=clen; first=lba if first is None else first; last=lba; previous=lba; count+=1
        if f.read(1): die("trailing patch bytes")
    if count!=EXPECTED_CHANGED: die("final changed-sector accounting mismatch")
    ledger_sha=sha256_file(args.ledger)
    summary={"batch":316,"status":PASS,"goal":"CD1_100_PERCENT_CANDIDATE","authoritative_candidate_batch":309,"source_patch_batch":314,
      "lineage":{"pristine_sha256":PRISTINE_SHA256,"candidate_sha256":CANDIDATE_SHA256,"patch_sha256":patch_sha,"estimated_or_guessed_bytes":0},
      "ledger":{"format":"jsonl-canonical-v1","rows":count,"first_lba":first,"last_lba":last,"compressed_payload_bytes":compressed_total,"ledger_sha256":ledger_sha,"ledger_chain_sha256":chain.hexdigest(),"lba_set_sha256":sector_set_chain.hexdigest(),"candidate_sector_sha256_chain":decoded_chain.hexdigest()},
      "gates":{"strictly_increasing_unique_lba":"PASS","all_payloads_exact_2352":"PASS","changed_sector_accounting":f"{count}/{EXPECTED_CHANGED} PASS","trailing_bytes":0,"estimated_or_guessed_bytes":0}}
    args.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(PASS); print(f"rows={count}/{EXPECTED_CHANGED} PASS"); print("ledger_sha256="+ledger_sha)

if __name__=="__main__": main()
