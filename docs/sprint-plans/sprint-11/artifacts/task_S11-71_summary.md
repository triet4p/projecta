# Task Summary: S11-71 — Align the v0.6.0 Product Version

## Outcome

Aligned the release contract to `0.6.0` in the root version file, API
manifest and runtime, API `uv.lock`, web manifest and npm lockfile, and
Semantic Core `pom.xml`. The ontology version was not changed.

## Validation

- `python scripts/check_release_contract.py --tag v0.6.0` passed.
- Release-contract unit tests passed.

## Status

`DONE`
