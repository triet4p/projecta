# Task Summary: S12-25 — Pre-register Quality Thresholds

**Sprint:** Sprint 12

**Task:** S12-25

## Summary of Work

Pre-registered hard-invariant, semantic, business and operational thresholds
for G6, including exact-span, abstention, ontology mapping, graph/retrieval,
review acceptance, manual-baseline and blinded-review requirements.

## Files Modified

* [metrics.v1.md](../../../../evaluation/sprint-12/metrics.v1.md) - Metric definitions.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Threshold table and revision rule.
* [sprint-12.md](../../sprint-12.md) - Marked S12-25 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Thresholds are contract defaults before full corpus observation and may be
revised once before G3 only with written rationale.
