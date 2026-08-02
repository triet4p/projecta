# Task Summary: S5-17 — Add project-scoped entity-link context read

**Sprint:** Sprint 5
**Task:** S5-17

## Summary of Work

Added the finite Semantic Core `GET /v1/entities/link-context` read. It uses
trusted project context, an allowlisted set of entity types, a hard limit of
1–100 (default 50), and returns only opaque IDs, types, and labels from the
trusted project's asserted graph. The Python client validates the bounded
response and exposes no arbitrary SPARQL or cross-project data.

## Files Modified

- `services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java`
- `services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java`
- `apps/api/src/projecta_api/semantic_core.py`
- `apps/api/tests/test_entity_link_context.py`

## Testing

- **Python:** contract test added; full async HTTP test is covered by later system tests.
- **Java:** compile/integration validation is included in the Semantic Core suite.
- **Static:** `git diff --check` passed.
