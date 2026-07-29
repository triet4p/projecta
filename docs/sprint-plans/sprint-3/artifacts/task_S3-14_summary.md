# Task Summary: S3-14 — Implement transactional rejection

**Sprint:** Sprint 3
**Task:** S3-14

## Summary of Work

Implemented transactional candidate rejection. A successful rejection updates
the candidate's current status and retained reason, records a reviewer-attributed
rejection activity in provenance, and writes nothing to the asserted graph.
Identical in-process idempotency-key replays return the original activity rather
than creating another one.

## Files Modified

- `services/semantic-core/src/main/java/org/projecta/semanticcore/CandidateRejectionService.java`
- `services/semantic-core/src/test/java/org/projecta/semanticcore/CandidateRejectionServiceTest.java`
- `docs/sprint-plans/sprint-3.md`

## Testing

- **Test File:** `CandidateRejectionServiceTest.java`
- **Status:** Passed (12 tests; compiler, formatter, and Maven enforcer checks).
- **Execution Command:** `docker build --target test -t projecta-semantic-core:s3-14-test ./services/semantic-core`

## Additional Notes

- Idempotency state is presently process-local because the operational store is
  outside this task's scope. S3-17 must replace or exercise it through the
  persistent transactional implementation required by the API contract.
