# S5-31 — Compatibility and image validation

Validation evidence:

- Docker Compose configuration: passed with `docker compose config --quiet`.
- Canonical ontology container: passed all 119 checks, including approved v0.4.
- Semantic Core compile: passed with `mvn -q -DskipTests compile`.
- Semantic Core non-TDB2 suite: passed with `mvn -q -Dtest='*Test,!Tdb2LifecycleIntegrationTest' test`.
- API suite: 45 passed, 2 skipped.
- Ruff: passed. Pyright: 0 errors, 0 warnings, 0 informations.
- Offline M3 replay evaluation: 8 cases passed; schema validity, precision/recall/F1, exact spans, bounded cross-project rejection, and abstention metrics were all 1.0.

The full Maven suite remains subject to the known Windows TDB2 integration-test cleanup lock: assertions pass, but JUnit temporary directories can remain locked during teardown. The existing system-test script still provides the canonical container path for Linux/CI cleanup semantics.
