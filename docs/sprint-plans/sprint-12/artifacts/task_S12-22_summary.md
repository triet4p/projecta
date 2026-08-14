# Task Summary: S12-22 — Define Split and Custody Procedure

**Sprint:** Sprint 12

**Task:** S12-22

## Summary of Work

Defined stratified 60/20/20 atomic and 12/6/6 scenario splits, development and
validation usage, human custody of test inputs/gold, digest publication,
pre-G6 unlock, one blinded run, resealing and invalidation conditions.

## Files Modified

* [data-governance.v1.md](../../../../evaluation/sprint-12/data-governance.v1.md) - Split and custody protocol.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Split acceptance boundary.
* [sprint-12.md](../../sprint-12.md) - Marked S12-22 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

The repository records contract/count/digest metadata only; no test payload or
gold is added in Phase B.
