# Batch 231 — Exact story payload recovery gate

## Completed

Added an exact-SHA recovery manifest and recursive file/ZIP scanner for the six story replacement payloads that currently block Disc 1 cumulative integration:

- SK0501.BIN — `6edc5467e1f5dcbd2e513f06003d17b9c59ddc314a8b325ebba66855b911d743`
- SK0502.BIN — `0b31fca7e96c3e60da04083981fba4624f3dd516dff604ae075d2f52d05da7bc`
- SK0503.BIN — `c844f857de7260e0b2746d7702460709393d8b08821986129cc5e09de103e76b`
- SKCM02.BIN — `0a2d0edf358b8fe6ab6edbc058e7e1263fc466706312bec43fd9994eb38419d9`
- SKCM04.BIN — `c3e78d0b32b87d58d720c0fdd616fbc2fba232b306abe8c528d66a524664c4f8`
- SKCM05.BIN — `cfd966f1cc1783f0da0f988aba92bd7591237cacb10c633da0063ce1f71c29f4`

The scanner only accepts byte-exact SHA-256 matches and copies recovered payloads into a clean output directory. It does not synthesize or estimate bytes.

## Preserved gates

1. Exact source/replacement SHA-256
2. Expected Write before Disc modification
3. LBA collision audit
4. MODE1/2352 EDC/ECC regeneration and verification
5. Re-extraction SHA-256 equality

## Current result

File Library contains manifests, QA workbooks and SHA ledgers proving all six compiled targets existed historically, but the six replacement binary bodies were not directly returned by current Library search. The new scanner is therefore the next executable recovery step against archived folders/ZIP packages before cumulative Disc integration.
