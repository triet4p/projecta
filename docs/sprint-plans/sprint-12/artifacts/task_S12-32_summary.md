# Task Summary: S12-32 — Calibrate Annotators

**Sprint:** Sprint 12

**Task:** S12-32

## Summary of Work

Defined the calibration procedure for language/domain qualification, common
examples, conflicts, isolated labeling and guide clarification. The procedure
explicitly withholds pilot labels and future held-out gold from calibration.

## Files Modified

* [calibration-protocol.v1.md](../../../../evaluation/sprint-12/pilot/calibration-protocol.v1.md) - Calibration and qualification protocol.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - Human evidence requirements.
* [sprint-12.md](../../sprint-12.md) - Marked S12-32 complete.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The agent fixture exercises the protocol but cannot establish human
qualification.
