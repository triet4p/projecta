# S12-R02 — Version the metric contract

Published metric contract v2 for future Sprint 12 runs. Relation semantic F1
now has an explicit identity over predicate and canonical endpoints, while
relation evidence support and exact-span quality are separate metrics with
explicit denominators and `not-applicable` handling for zero semantic matches.

The historical v1 contract, evaluator v2, f07/f08 reports and R01 audit remain
immutable. Provider execution remains blocked pending instrumentation repair in
S12-R03 and G3.1-A approval.

## Files Modified

- `evaluation/sprint-12/harness/metric-contract.v2.json` — versioned machine-
  readable formulas, denominators, aggregation and custody rules.
- `evaluation/sprint-12/harness/metrics.v2.md` — human-readable metric contract.
- `evaluation/sprint-12/README.md` — publishes the v2 contract entry point.
- `scripts/tests/test_sprint12_metric_contract_v2.py` — contract and historical
  immutability tests.
- `docs/sprint-plans/sprint-12.md` — marks S12-R02 complete only.

## Testing

- **Test File:** `scripts/tests/test_sprint12_metric_contract_v2.py`
- **Status:** Passed
- **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_metric_contract_v2.py`

## Additional Notes

S12-R03 must implement the evaluator/instrumentation changes and fixtures. This
task deliberately does not regenerate provider reports or modify historical
evidence.
