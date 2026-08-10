# Task Summary: Restore Graph node-detail selection

**Sprint:** Sprint 9 — Provider Runtime Truthfulness
**Task:** S9-14

## Summary of Work

Removed private Semantic Core HTTP status metadata before the strict
`GraphNodeDetail` projection validates a selected node. This restores the Graph
click journey without weakening the public model or accepting arbitrary fields.

## Files Modified

* `apps/api/src/projecta_api/graph_projection.py`
* `apps/api/tests/test_graph_projection.py`
* `.agents/memory/lessons-learned.md`
* `docs/sprint-plans/sprint-9.md`

## Testing

* API: `127 passed, 3 skipped`; Pyright and Ruff clean.
* Web: 15 tests; typecheck and lint pass.
* Runtime: all 7 existing handles returned HTTP 200, covering `Note`,
  `NoteItem`, `Requirement`, `Task`, and `ResearchFinding`.
* Browser: candidate and Note detail panels rendered after real clicks; no
  fail-safe error banner remained.

## Additional Notes

The public node-detail contract remains fail-explicit and `extra="forbid"`.
