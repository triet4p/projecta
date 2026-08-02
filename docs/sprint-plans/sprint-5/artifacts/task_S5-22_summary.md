# Task Summary: S5-22 — Extend atomic candidate ingestion

**Sprint:** Sprint 5
**Task:** S5-22

## Summary of Work

Added the Semantic Core M3 ingestion operation and HTTP route. The service
validates allowlisted entity types/predicates, creates source evidence,
entity/relation/link candidate records and extraction provenance, validates
the complete payload before mutation, and writes all graphs plus idempotency
record in one conditional Fuseki update. Replays return the existing outcome;
validation or storage failure prevents partial writes.

## Files Modified

- `services/semantic-core/src/main/java/org/projecta/semanticcore/LlmCandidateIngestionService.java`
- `services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java`
- `services/semantic-core/src/test/java/org/projecta/semanticcore/LlmCandidateIngestionServiceTest.java`

## Testing

- **Test:** unsupported type fails before mutation.
- **Java integration:** included in the Maven Semantic Core suite.
- **Static:** `git diff --check` passed.
