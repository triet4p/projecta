# Task Summary: S3-15 — Implement project-scoped query APIs

**Sprint:** Sprint 3
**Task:** S3-15

## Summary of Work

Added typed, finite query APIs for current asserted knowledge, candidate history,
and asserted-item evidence. Every query derives its named graph from the trusted
`ProjectId`; it accepts neither graph IRIs nor SPARQL and rejects unallowlisted
types and out-of-scope evidence chains.

## Files Modified

- `services/semantic-core/src/main/java/org/projecta/semanticcore/ProjectScopedQueryService.java`
- `services/semantic-core/src/test/java/org/projecta/semanticcore/ProjectScopedQueryServiceTest.java`
- `docs/sprint-plans/sprint-3.md`

## Testing

- **Status:** Passed (15 unit tests).
- **Execution Command:** `docker run --rm -v "${PWD}/services/semantic-core:/workspace" projecta-semantic-core:s3-15-development mvn --batch-mode test`

## Additional Notes

- HTTP adapter and error-schema contract tests remain S3-16 scope.
