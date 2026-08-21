# S12-R01 — Publish the core-quality audit

Published a new digest-bound, sanitized core-quality audit for the Sprint 12
G3.1 remediation track. The audit binds the atomic/scenario v2 corpora, metric
and error contracts, evaluator, baseline and scoring erratum, f08 aggregate,
registry/G5 closure, and all six f08 case-run reports without changing any
historical evidence.

## Files Modified

- `evaluation/sprint-12/audit/core-quality-audit.v1.json` — machine-readable
  evidence binding and diagnostic findings.
- `evaluation/sprint-12/audit/core-quality-audit.v1.md` — reviewable audit
  summary and decision boundary.
- `scripts/tests/test_sprint12_core_quality_audit.py` — digest, sanitization,
  corpus, scenario, f08, and plan-state contract tests.
- `docs/sprint-plans/sprint-12.md` — marks S12-R01 complete only.

## Testing

- **Test File:** `scripts/tests/test_sprint12_core_quality_audit.py`
- **Status:** Passed
- **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_core_quality_audit.py`

## Additional Notes

The semantic relation decomposition remains explicitly diagnostic, not an
official metric. G3.1-A still requires the metric contract and evaluator
fixtures to be repaired before any provider execution.
