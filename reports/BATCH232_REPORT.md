# Batch 232 — CD1 story payload deterministic rebuild preparation

## Completed

- Froze the six missing story replacement targets into one exact rebuild contract.
- Added exact source Disc 1 SHA-256 and exact UnDotum.ttf SHA-256 requirements.
- Added MODE1/2352 raw-sector extraction for the six pristine source assets.
- Added translation-ledger verification for B57/B58/B60/B62 records and historical compiled SHA-256 values.
- Added direct-file and ZIP-member exact compiled-payload recovery by SHA-256.
- The tool never accepts guessed bytes: a recovered compiled payload is accepted only when its full SHA-256 equals the historical target hash.
- Batch232 performs no Disc write. After all six compiled payloads are recovered/rebuilt, the existing Expected Write -> LBA collision -> EDC/ECC -> re-extraction gate remains mandatory.

## Six exact compiled targets

| Asset | Expected compiled SHA-256 |
|---|---|
| SK0501.BIN | `6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743` |
| SK0502.BIN | `0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc` |
| SK0503.BIN | `c844f857de7260e0b2746d7702460709393d8b08821986129cc5e09de103e76b` |
| SKCM02.BIN | `0a2d0edf358b8fe6ab6edbc058e7e1263fc466706312bec43fd9994eb38419d9` |
| SKCM04.BIN | `c3e78d0b32b87d58d720c0fdd616fbc2fba232b306abe8c528d66a524664c4f8` |
| SKCM05.BIN | `cfd966f1cc1783f0da0f988aba92bd7591237cacb10c633da0063ce1f71c29f4` |

## Current blocker

File Library retains the translation ledgers, source metadata, validation records, and historical target hashes, but the six byte-exact compiled BIN bodies were not found in the current recovery search. The pristine Disc1 bytes are historically proven, but are not mounted to this automation runtime as a raw file. Therefore Batch232 stops before any speculative compiler output or Disc write.

Exact next input needed for immediate continuation: either (A) any file/ZIP containing one or more of the six compiled payload hashes above, or (B) the pristine Disc1 BIN plus exact UnDotum.ttf and the four translation-ledger JSON files so the rebuild preparation gate can produce verified pristine source extracts and hand off to the historical compiler reconstruction step.
