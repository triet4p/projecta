# Task Summary: S8-45 — Candidate review queue

**Sprint:** Sprint 8
**Task:** S8-45

## Summary of Work
Added a project-scoped pending candidate queue with human labels, source excerpts, proposed type/relations, validation state, confidence, age, evidence count, and selection-based review entry.

## Files Modified
* [apps/web/src/screens/ReviewScreen.tsx](F:/ai-ml/projecta/apps/web/src/screens/ReviewScreen.tsx) — queue and selection workflow.
* [apps/api/src/projecta_api/graph_projection.py](F:/ai-ml/projecta/apps/api/src/projecta_api/graph_projection.py) — candidate queue DTO.

## Testing
* **Status:** Passed
* **Execution:** `uv run pytest -q` from `apps/api`; frontend lint/typecheck/tests.
