# Task Summary: Fuseki correlated diagnostics

**Sprint:** Sprint 8
**Task:** S8-20

## Summary of Work

Instrumented `FusekiGateway` with safe dependency start/completed/failed
diagnostics. Query, update, and named-graph operations now carry the current
request/operation correlation, enforce a 10-second request timeout, report
upstream status and latency, and compute SELECT/graph result cardinality
without logging SPARQL, RDF, graph IRIs, or response bodies. Semantic Core
binds correlation metadata at the request boundary.

## Files Modified

* [FusekiGateway.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiGateway.java) - Correlated Fuseki diagnostics, timeout, and cardinality.
* [SemanticCoreApplication.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java) - Request-bound gateway correlation.
* [FusekiGatewayTest.java](../../../../services/semantic-core/src/test/java/org/projecta/semanticcore/FusekiGatewayTest.java) - Correlation binding regression.

## Testing

* **Test File:** Semantic Core Maven test suite.
* **Status:** Passed.
* **Execution Command:** `mvn --batch-mode "-Dspotless.check.skip=true" test`

## Additional Notes

The gateway remains service-authored and does not accept client SPARQL or
graph identifiers as logging metadata.
