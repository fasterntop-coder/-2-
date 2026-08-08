# Batch 234 — Historical raw-disc recovery expansion

## Completed

- Added recovery of the six exact missing story payloads directly from historical MODE1/2352 Disc1 images.
- Reads each target from its exact ISO LBA and exact byte size from the Batch232 contract.
- Verifies every contributing raw sector with the repository MODE1 EDC/ECC verifier before accepting extracted bytes.
- Classifies each extracted extent as pristine source, exact compiled target, other historical variant, or read/EDC/ECC failure.
- Writes a recovered asset only when the full extracted payload SHA-256 equals the historical compiled SHA-256.
- Performs no Disc write and commits no copyrighted asset bytes.

## Why this advances the blocker

Batch231/232 could recover only standalone files, ZIP members, or rebuild inputs. Batch234 can now recover the same six byte-exact compiled assets from any retained historical full Disc1 BIN even when the asset files were never separately archived.

## Required acceptance chain

1. Raw source sectors: MODE1/2352 sync/mode/EDC/ECC-P/ECC-Q PASS.
2. Extracted extent: exact LBA + exact byte size.
3. Payload: exact historical compiled SHA-256.
4. After all six are recovered: Expected Write -> LBA collision -> patched MODE1 EDC/ECC -> exact re-extraction SHA-256.

No estimated or inferred payload bytes are accepted.
