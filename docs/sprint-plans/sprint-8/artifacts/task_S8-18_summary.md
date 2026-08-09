# Task Summary: Semantic Core fail-explicit handlers

**Sprint:** Sprint 8
**Task:** S8-18

## Summary of Work

Hardened the Semantic Core error boundary for malformed HTTP requests,
persistence/store failures, invalid query results, lifecycle failures, and
unexpected exceptions. Mappings now use finite taxonomy codes such as
`PERSISTENCE_UNAVAILABLE` and `QUERY_FAILED`, retain sanitized public detail,
and emit a safe terminal structured log with request/operation correlation and
outcome. No exception message, SPARQL, RDF, graph path, or storage detail is
serialized.

## Files Modified

* [ApiErrorTranslator.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/ApiErrorTranslator.java) - Typed parse/store/query/lifecycle mappings.
* [SemanticCoreApplication.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java) - Safe terminal failure event and response boundary.
* [ApiErrorTranslatorTest.java](../../../../services/semantic-core/src/test/java/org/projecta/semanticcore/ApiErrorTranslatorTest.java) - Persistence/query mapping regressions.

## Testing

* **Test File:** Semantic Core Maven test suite.
* **Status:** Passed.
* **Execution Command:** `mvn --batch-mode "-Dspotless.check.skip=true" test`

## Additional Notes

This task does not change Fuseki transaction behavior; it makes failures at
that boundary explicit and safe. Gateway diagnostics and operation events are
implemented in S8-19/S8-20.
