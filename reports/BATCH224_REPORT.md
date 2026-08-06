# Batch 224 — SYS22 exact input closure

## Result

`SYS22` cannot yet be promoted into the runtime candidate because the exact patched MODE1/2352 payload is absent from the currently visible File Library material.

The B116/B117/B118 applicator scripts were inspected as data-only provenance. They contain sector names and SHA-256 oracles, but not the 2,352-byte sector payloads.

## Exact target

- asset: `SYS22`
- LBA: `207446`
- logical size: `82,030`
- replacement SHA-256: `d4bbcd86442f82295afd1631548a56030e0c791e74477b3ac96e31fb2db6c976`
- required patched raw sectors: `29`
- LBA range represented: `207446..207473`, plus `207478`

## Accepted recovery input

Any one of the following is sufficient:

1. the 29 exact raw-sector sidecars listed in `manifests/SYS22_EXACT_SECTOR_INPUT_REQUIREMENTS.json`;
2. a ZIP containing all 29 sectors with matching patched SHA-256 values;
3. a MODE1/2352 checkpoint BIN containing those exact sectors at the listed LBAs.

No estimated bytes were generated and no Disc image was written.
