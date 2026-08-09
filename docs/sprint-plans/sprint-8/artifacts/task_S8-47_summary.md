# Task Summary: S8-47 — ID-free Knowledge workflows

**Sprint:** Sprint 8
**Task:** S8-47

## Summary of Work
Refactored Knowledge to browse a returned labeled collection and open detail, evidence, and lifecycle views from selection. Removed candidate/item ID inputs and raw-ID-first labels from Knowledge, Capture, and Extraction UI paths.

## Files Modified
* [apps/web/src/screens/KnowledgeScreen.tsx](F:/ai-ml/projecta/apps/web/src/screens/KnowledgeScreen.tsx) — collection and split detail view.
* [apps/api/src/projecta_api/graph_projection.py](F:/ai-ml/projecta/apps/api/src/projecta_api/graph_projection.py) — ID-free collection contract.
* [services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java](F:/ai-ml/projecta/services/semantic-core/src/main/java/org/projecta/semanticcore/FusekiQueryService.java) — knowledge handle resolution.

## Testing
* **Status:** Passed
* **Execution:** `uv run pytest -q` from `apps/api`; `npm test -- --run` from `apps/web`.
