# Task Summary: S12-24 — Define Metric Implementations

**Sprint:** Sprint 12

**Task:** S12-24

## Summary of Work

Defined case-level exact metrics for types, relations, links, evidence,
abstention, ontology mapping, graph checkpoints and grounded answers, plus
business/operational metrics, denominators, slice reporting, confidence
intervals and missing-output handling.

## Files Modified

* [metrics.v1.md](../../../../evaluation/sprint-12/metrics.v1.md) - Metric formulas and reporting contract.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Metric gate binding.
* [sprint-12.md](../../sprint-12.md) - Marked S12-24 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Missing and malformed outputs remain denominator-visible failures.
