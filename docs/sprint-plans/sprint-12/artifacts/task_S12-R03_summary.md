# S12-R03 — Repair relation error buckets

Reworked relation instrumentation to version `s12.relation-instrumentation.v3`
with a fixed exclusive precedence: semantic identity matches are classified as
exact or wrong-span first, followed by reversed/missing/wrong endpoints,
wrong-predicate, and finally missing/extra relations. Every gold and predicted
relation is consumed by at most one bucket, and reconciliation totals prove
that bucket counts equal the gold and predicted denominators.

## Files Modified

- `scripts/sprint12_evaluator.py` — v3 evaluator and mutually exclusive
  relation instrumentation.
- `evaluation/sprint-12/harness/README.md` — documents evaluator and
  instrumentation v3 while preserving historical versions.
- `scripts/tests/test_sprint12_relation_instrumentation_v3.py` — fixtures for
  exact, wrong-span, wrong-predicate, reversed, wrong-endpoint, missing and
  extra relation cases.
- `scripts/tests/test_sprint12_f07_execution_contract.py` — binds the current
  instrumentation version to v3.
- `docs/sprint-plans/sprint-12.md` — marks S12-R03 complete only.

## Testing

- **Test File:** `scripts/tests/test_sprint12_relation_instrumentation_v3.py`
- **Status:** Passed
- **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_relation_instrumentation_v3.py`

## Additional Notes

Historical f07/f08 reports remain bound to their original instrumentation
versions. This repair is offline and does not authorize provider execution;
sanitized per-case signature persistence remains S12-R04.
