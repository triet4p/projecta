# Task Summary: S5-26 — Add Semantic Core ingestion tests

**Sprint:** Sprint 5
**Task:** S5-26

## Summary of Work

Added M3 ingestion coverage for fail-closed unsupported entity types before
mutation, canonical candidate IRIs, v0.4 SHACL loading, target isolation, and
no-persistence-on-failure; ran the Semantic Core transaction, provenance,
replay, and isolation suite alongside it.

## Files Modified

- `services/semantic-core/src/test/java/org/projecta/semanticcore/LlmCandidateIngestionServiceTest.java`

## Testing

- **Passed:** `mvn -q -Dtest='*Test,!Tdb2LifecycleIntegrationTest' test`.
- **Known environment failure:** full `mvn -q test` reached 29 tests with 0
  assertion failures but two existing `Tdb2LifecycleIntegrationTest` cases
  errored while JUnit tried to delete locked Windows temp-store files. This is
  a cleanup/runtime lock issue, not an M3 assertion failure, and remains a
  Sprint 5 review risk.
- **Static:** `git diff --check` passed.
