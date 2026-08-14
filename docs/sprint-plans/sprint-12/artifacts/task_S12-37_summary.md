# Task Summary: S12-37 — Re-run Pilot Agreement

**Sprint:** Sprint 12

**Task:** S12-37

## Summary of Work

Documented the fresh-subset rerun procedure, but did not execute a fresh
subset. The synthetic fixture has no independent scenario or question-answer
labels and cannot substitute for the required rerun, so S12-37 is reopened.

## Files Modified

* [agreement-report.v1.json](../../../../evaluation/sprint-12/pilot/agreement-report.v1.json) - Provisional rerun metrics.
* [annotation-guide.v1.1.md](../../../../evaluation/sprint-12/pilot/annotation-guide.v1.1.md) - Fresh-subset rerun requirement.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - G2 blocking human evidence.
* [sprint-12.md](../../sprint-12.md) - Reopened S12-37 pending fresh rerun.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The rerun procedure is implemented as a contract; fixture results are not
human agreement evidence.
