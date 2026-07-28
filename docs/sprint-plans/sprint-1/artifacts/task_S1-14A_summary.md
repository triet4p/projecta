# Task Summary: S1-14A — Normalize Repository Layout

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-14A — Normalize repository layout

## Summary of Work

Reconciled the Sprint 1 implementation with the approved repository and
Compose-first deployment structures. Removed parallel root-level entry points
and kept semantic content unchanged.

## Canonical Locations

| Concern | Canonical location |
|---|---|
| Base and environment Compose files | `compose.yaml`, `compose.dev.yaml`, `compose.prod.yaml` |
| Jena/Fuseki image and config | `infra/docker/fuseki/` |
| Executable validation | `scripts/validate_ontology.py` |
| Ontology governance docs | `docs/ontology/` |
| Sprint review evidence | `docs/sprint-plans/sprint-1/` |

The obsolete root `docker/`, `artifacts/`, `docker-compose.yml`, and generated
`ontology/hsperfdata_root/` paths were removed after their contents were moved or
merged.

## Validation

- `docker compose run --build --rm ontology-test` — 32/32 checks passed.
- `docker compose --profile tools -f compose.yaml -f compose.dev.yaml config` —
  Compose topology resolves successfully.
- Python syntax compilation — passed.
- Local Markdown link resolution — passed.

The latest layout and Docker-native validation decisions were appended to
`.agents/memory/decisions.md`; reusable environment findings were appended to
`.agents/memory/lessons-learned.md`.
