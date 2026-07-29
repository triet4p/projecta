# Task Summary: S3-12 — Implement candidate loading and validation

**Sprint:** Sprint 3
**Task:** S3-12

## Summary of Work

Implemented read-only candidate-graph loading and Jena SHACL validation with
structured violations. The service resolves the candidates graph from trusted
project context and does not mutate asserted or provenance graphs.

## Files Modified

- `CandidateValidationService.java`
- `CandidateValidationResult.java`
- `CandidateValidationServiceTest.java`
- `docs/sprint-plans/sprint-3.md`

## Testing

- **Status:** Passed.
- **Execution Command:** containerized `mvn --batch-mode verify`.

## Additional Notes

- Test coverage verifies an invalid candidate returns its SHACL message while
  asserted and provenance graphs remain empty.
