# Task Summary: S3-16 — Add unit and contract tests

**Sprint:** Sprint 3
**Task:** S3-16

## Summary of Work

Added a stable API-problem model and contract-safe error translator. Unit tests
now cover invalid input, project-scoped not-found behavior, idempotency-key
reuse, invalid lifecycle state, and unexpected failures without exposing
internal graph or Fuseki details.

## Files Modified

- `services/semantic-core/src/main/java/org/projecta/semanticcore/ApiProblem.java`
- `services/semantic-core/src/main/java/org/projecta/semanticcore/ApiErrorTranslator.java`
- `services/semantic-core/src/test/java/org/projecta/semanticcore/ApiErrorTranslatorTest.java`
- `docs/sprint-plans/sprint-3.md`

## Testing

- **Status:** Passed (18 tests; Maven enforcer and Spotless checks included).
- **Execution Command:** `docker build --target test -t projecta-semantic-core:s3-16-test ./services/semantic-core`

## Additional Notes

- Persistent-store and HTTP transport integration remain S3-17 scope.
