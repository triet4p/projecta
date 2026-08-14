# Task Summary: S12-32 — Calibrate Annotators

**Sprint:** Sprint 12

**Task:** S12-32

## Summary of Work

Prepared the calibration procedure for language/domain qualification, common
examples, conflicts, isolated labeling and guide clarification. No qualified
human calibration was run, so S12-32 is reopened; the procedure alone is not
the required evidence.

## Files Modified

* [calibration-protocol.v1.md](../../../../evaluation/sprint-12/pilot/calibration-protocol.v1.md) - Calibration and qualification protocol.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - Human evidence requirements.
* [sprint-12.md](../../sprint-12.md) - Reopened S12-32 pending human calibration.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The agent fixture exercises the protocol but cannot establish human
qualification.
