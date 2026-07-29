# Task Summary: S3-08 — Add the persistent Fuseki service

**Sprint:** Sprint 3
**Task:** S3-08

## Summary of Work

Added the canonical persistent Fuseki/TDB2 service, a health check, and a
separate idempotent ontology-bootstrap service. The bootstrap uses Fuseki's
HTTP Graph Store endpoint, preserving the single-owner TDB2 constraint and
leaving the tools-only `jena` service separate.

## Files Modified

- [compose.yaml](../../../../compose.yaml) - Fuseki, bootstrap, health, and named-volume topology.
- [infra/docker/fuseki/config/fuseki-config.ttl](../../../../infra/docker/fuseki/config/fuseki-config.ttl) - TDB2-backed Fuseki dataset configuration.
- [scripts/bootstrap_fuseki.py](../../../../scripts/bootstrap_fuseki.py) - idempotent released-ontology loader.
- [.agents/memory/lessons-learned.md](../../../../.agents/memory/lessons-learned.md) - UV-managed Python entrypoint lesson.
- [docs/sprint-plans/sprint-3.md](../../../../docs/sprint-plans/sprint-3.md) - records task completion.

## Testing

- **Status:** Passed.
- **Execution Commands:**

  - `docker compose -f compose.yaml config`
  - `docker compose -f compose.yaml up --build --wait fuseki`
  - `docker compose -f compose.yaml run --rm fuseki-bootstrap`
  - Read-only HTTP/SPARQL count inside Fuseki: **142 triples** in `https://w3id.org/projecta/data/ontology/v/0.2/`.

## Additional Notes

- The local `projecta-fuseki-1` container and `projecta_fuseki-data` volume are
  intentionally running/preserved to exercise persistent local storage.
