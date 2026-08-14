# Task Summary: S12-16 — Freeze Minimum Quotas

**Sprint:** Sprint 12

**Task:** S12-16

## Summary of Work

Recorded minimums of 200 atomic cases and 24 longitudinal episodes, 60/20/20
and 12/6/6 splits, language minimums, 25% development double annotation,
100% validation/test double annotation and 60% human-authored origin.

## Files Modified

* [coverage-matrix.v1.json](../../../../evaluation/sprint-12/coverage-matrix.v1.json) - Machine-readable quotas.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Quota interpretation and headroom.
* [sprint-12.md](../../sprint-12.md) - Marked S12-16 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Quotas remain contract minimums and do not claim that authoring capacity or
qualified annotators are already available.
