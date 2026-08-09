# Task Summary: Semantic Core lifecycle and query events

**Sprint:** Sprint 8
**Task:** S8-19

## Summary of Work

Added a Semantic Core operation event logger with allowlisted route classes and
global before/after hooks. Capture, validation, confirmation, rejection,
knowledge/evidence queries, project context, inference, graph projection, and
health routes now have correlated start/completed coverage; typed failures also
emit a failed event. Route parameters and request paths are never logged.

## Files Modified

* [OperationEventLogger.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/OperationEventLogger.java) - Safe route classification and correlated events.
* [SemanticCoreApplication.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java) - Global HTTP lifecycle hooks and failure event integration.
* [OperationEventLoggerTest.java](../../../../services/semantic-core/src/test/java/org/projecta/semanticcore/OperationEventLoggerTest.java) - Route allowlist/redaction-boundary tests.

## Testing

* **Test File:** Semantic Core Maven test suite.
* **Status:** Passed.
* **Execution Command:** `mvn --batch-mode "-Dspotless.check.skip=true" test`

## Additional Notes

The logger emits safe key/value structured metadata to the configured logging
backend; it does not persist semantic facts or serialize path identifiers.
