# Task Summary: S1-12 — Add the Jena Test Runner

**Sprint:** Sprint 1 — Ontology Kernel
**Task:** S1-12 — Add the Jena Test Runner

## Summary of Work

Created a Docker-native Apache Jena test service that validates ontology syntax,
vocabulary invariants, competency queries, and negative fixtures. The service
uses a custom image built from `infra/docker/fuseki/Dockerfile` with Jena 6.1.0,
Fuseki 6.1.0, Python 3, and rdflib on Eclipse Temurin 21 JRE.

**Why Docker instead of host install:**
Per user preference, Jena/Fuseki is not installed on the host machine. The Docker image provides `riot`, `sparql`, `tdb2.tdbloader`, `shacl`, and all other Jena CLI tools without polluting the host environment. This is consistent with the Docker Compose deployment decision recorded in `.agents/memory/decisions.md`.

**Test runner**
([scripts/validate_ontology.py](../../../../scripts/validate_ontology.py)):

| Step | Tool | What it checks |
|---|---|---|
| 1. Build and run | `docker compose run --build --rm ontology-test` | Builds the pinned image and starts the disposable test service |
| 2. Syntax validation | Jena `riot --validate` | Two ontology modules plus positive and negative TriG fixtures |
| 3. Vocabulary assertions | rdflib | Exact class, property, and controlled-individual counts |
| 4. SPARQL regression | rdflib | All 14 competency queries with exact row/ASK expectations |
| 5. Negative testing | rdflib | Each detector is false on clean data and true on its bad fixture |

## Files Created / Modified

- [infra/docker/fuseki/Dockerfile](../../../../infra/docker/fuseki/Dockerfile) — New: Jena 6.1.0 + Fuseki 6.1.0 on `eclipse-temurin:21-jre-jammy`. Downloads official Apache binary distributions, sets PATH, exposes port 3030.
- [compose.yaml](../../../../compose.yaml) — Canonical `jena` tool service and disposable `ontology-test` service.
- [scripts/validate_ontology.py](../../../../scripts/validate_ontology.py) — Container entry point for the complete Sprint 1 suite.
- [.agents/memory/lessons-learned.md](../../../../.agents/memory/lessons-learned.md) — Docker, TriG, pip compatibility, and host-shell portability lessons.

## Testing

The canonical run passes 32/32 checks:

- 6/6 Jena syntax checks.
- 4/4 vocabulary-count assertions.
- 14/14 competency queries.
- 3/3 negative detectors return false on clean data and true on their
  corresponding fixture.
- 2/2 query inventory guards.

**Execution command:**
`docker compose run --build --rm ontology-test`

**Checks not run:** OWL consistency (no reasoner configured — out of Sprint 1 scope); SHACL conformance (shapes not yet created — S2).

## Additional Notes

- **TriG named-graph handling:** The canonical fixture remains TriG; no duplicate Turtle workaround is maintained. The Python validator uses `rdflib.Dataset` as recorded in lessons learned.
- **Canonical entry point:** The root `compose.yaml` owns the complete test
  service; no parallel Compose manifest or host Bash dependency is maintained.
- **Image version:** `projecta-jena:6.1.0` is pinned to Jena 6.1.0 (May 2026). The Dockerfile `ARG JENA_VERSION` allows overriding at build time.
- **Fuseki included:** The image includes Fuseki server for future use (Sprint 3+ service layer). Not used by the Sprint 1 test runner.
