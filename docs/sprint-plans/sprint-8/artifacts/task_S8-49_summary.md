# Task Summary: S8-49 — Graph performance and safety limits

**Sprint:** Sprint 8
**Task:** S8-49

## Summary of Work
Enforced published node/edge budgets, deterministic ordering, explicit continuation/partial fields, bounded one-hop expansion, raw-handle rejection, cyclic graph acceptance without recursive traversal, stale-state rendering, and AbortController cancellation for superseded graph loads.

## Files Modified
* [apps/api/src/projecta_api/graph_projection.py](F:/ai-ml/projecta/apps/api/src/projecta_api/graph_projection.py) — budget and projection integrity checks.
* [apps/web/src/api/client.ts](F:/ai-ml/projecta/apps/web/src/api/client.ts) — abortable request support.
* [apps/web/src/screens/GraphScreen.tsx](F:/ai-ml/projecta/apps/web/src/screens/GraphScreen.tsx) — cancellation and explicit boundary states.
* [apps/api/tests/test_graph_projection.py](F:/ai-ml/projecta/apps/api/tests/test_graph_projection.py) — bounded cyclic/repeatability regression.

## Testing
* **Status:** Passed
* **Execution:** `uv run pytest -q` from `apps/api`; `mvn --batch-mode verify`; frontend lint/typecheck/tests.
* **Note:** Existing Sprint 7 Playwright journey remains a stale environment-dependent baseline because it assumes pre-Sprint-8 navigation and a running API proxy; it was not counted as a Sprint 8 pass.
