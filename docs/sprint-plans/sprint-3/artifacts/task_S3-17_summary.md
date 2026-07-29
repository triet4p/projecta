# Task Summary: S3-17 — Add Fuseki/TDB2 integration tests

**Sprint:** Sprint 3
**Task:** S3-17

## Summary of Work

Added an on-disk, temporary TDB2 integration suite. It verifies a rejection
persists across dataset reopen without an asserted write, and that a confirmed
candidate rejects a later conflicting rejection while inferred and asserted
named-graph boundaries remain isolated. Confirmation now records its terminal
candidate status inside the same transaction.

## Files Modified

- `services/semantic-core/pom.xml`
- `services/semantic-core/src/main/java/org/projecta/semanticcore/CandidateConfirmationService.java`
- `services/semantic-core/src/test/java/org/projecta/semanticcore/Tdb2LifecycleIntegrationTest.java`
- `docs/sprint-plans/sprint-3.md`

## Testing

- **Status:** Passed (20 tests; formatter and Maven enforcer checks included).
- **Execution Command:** `docker run --rm -v "${PWD}/services/semantic-core:/workspace" projecta-semantic-core:s3-17-development mvn --batch-mode verify`

## Additional Notes

- The suite uses a JUnit temporary TDB2 directory and never touches the Compose
  developer volume. Remote Fuseki orchestration belongs to S3-18.
