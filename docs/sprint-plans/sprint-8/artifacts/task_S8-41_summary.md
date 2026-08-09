# Task Summary: S8-41 — Graph projection endpoints

**Sprint:** Sprint 8
**Task:** S8-41

## Summary of Work
Exposed typed Application API endpoints for initial graph view, one-hop neighborhood, node detail, evidence, lifecycle, candidate queue, and ID-free knowledge workflows. Unknown filters, raw handles, excessive limits, graph names, and arbitrary query syntax are rejected at the boundary.

## Files Modified
* [apps/api/src/projecta_api/routes.py](F:/ai-ml/projecta/apps/api/src/projecta_api/routes.py) — public route validation and projection mapping.
* [apps/web/src/api/client.ts](F:/ai-ml/projecta/apps/web/src/api/client.ts) — typed client methods and response validation.
* [docs/architecture/application-api.sprint7.openapi.json](F:/ai-ml/projecta/docs/architecture/application-api.sprint7.openapi.json) — committed API snapshot.

## Testing
* **Status:** Passed
* **Execution:** `npm run check:api-drift` from `apps/web`; `uv run pytest -q` from `apps/api`
