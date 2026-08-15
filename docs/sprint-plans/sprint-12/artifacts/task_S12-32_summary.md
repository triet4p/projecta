# Task Summary: S12-32 — Calibrate Annotators

**Sprint:** Sprint 12

**Task:** S12-32

## Summary of Work

Executed the calibration procedure for the owner-delegated synthetic AI track
and bound the resulting review to explicit non-human provenance. This closes
the synthetic-track task without claiming qualified-human calibration.

## Files Modified

* [calibration-protocol.v1.md](../../../../evaluation/sprint-12/pilot/calibration-protocol.v1.md) - Calibration and qualification protocol.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - Human evidence requirements.
* [owner-delegated-ai-review.v1.json](../../../../evaluation/sprint-12/pilot/owner-delegated-ai-review.v1.json) - AI calibration review evidence.
* [sprint-12.md](../../sprint-12.md) - Recorded the owner-delegated amendment.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

Human qualification and inter-human reliability remain explicitly unclaimed.
