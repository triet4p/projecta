# Task Summary: S12-21 — Threat-model Dataset Leakage

**Sprint:** Sprint 12

**Task:** S12-21

## Summary of Work

Threat-modeled exact and near duplicates, multilingual lineage, prompt
contamination, model memorization, agent exposure, safe logs and metric
cherry-picking. Each threat has a preventive control and fail-closed response.

## Files Modified

* [data-governance.v1.md](../../../../evaluation/sprint-12/data-governance.v1.md) - Leakage threat matrix.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Leakage validation and gate boundary.
* [sprint-12.md](../../sprint-12.md) - Marked S12-21 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Any held-out exposure invalidates the affected result instead of being relabeled
as a successful evaluation.
