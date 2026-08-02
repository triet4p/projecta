# Task Summary: S5-23 — Implement the M3 API orchestration

**Sprint:** Sprint 5
**Task:** S5-23

## Summary of Work

Added the untyped Quick Note extraction route and orchestration service. The
flow obtains bounded project entity context, builds the versioned prompt,
calls the provider-neutral gateway, normalizes all output, and sends only the
normalized finite payload to Semantic Core for atomic persistence. FastAPI does
not mutate RDF and maps provider failures to sanitized public problems.

## Files Modified

- `apps/api/src/projecta_api/models.py`
- `apps/api/src/projecta_api/semantic_core.py`
- `apps/api/src/projecta_api/extraction/service.py`
- `apps/api/src/projecta_api/routes.py`
- `apps/api/src/projecta_api/main.py`
- `apps/api/tests/test_extraction_orchestration.py`

## Testing

- **Command:** `uv run pytest tests/test_extraction_orchestration.py -q`
- **Coverage:** context read → gateway → normalization → Core persistence ordering and missing-model fail-closed behavior.
