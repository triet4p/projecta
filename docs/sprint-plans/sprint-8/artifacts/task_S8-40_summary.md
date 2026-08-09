# Task Summary: S8-40 — Bounded graph queries

**Sprint:** Sprint 8
**Task:** S8-40

## Summary of Work
Added Semantic Core graph, neighborhood, node detail, evidence/lifecycle, candidate, and knowledge projection queries with deterministic ordering, node/edge budgets, same-project graph routing, and asserted/source-backed state flags.

## Files Modified
* [services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java](F:/ai-ml/projecta/services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java) — bounded Fuseki-backed projection queries.
* [services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java](F:/ai-ml/projecta/services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java) — private typed query routes and trusted project checks.

## Testing
* **Status:** Passed
* **Execution:** `mvn --batch-mode verify`
