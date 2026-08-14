# Task Summary: S12-37 — Re-run Pilot Agreement

**Sprint:** Sprint 12

**Task:** S12-37

## Summary of Work

Bound the fresh-subset rerun procedure and recorded that the synthetic fixture
meets the provisional type/abstention, span, relation/link and graph-state
thresholds after the guide revision. The packet keeps the human rerun as a
blocking G2 requirement.

## Files Modified

* [agreement-report.v1.json](../../../../evaluation/sprint-12/pilot/agreement-report.v1.json) - Provisional rerun metrics.
* [annotation-guide.v1.1.md](../../../../evaluation/sprint-12/pilot/annotation-guide.v1.1.md) - Fresh-subset rerun requirement.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - G2 blocking human evidence.
* [sprint-12.md](../../sprint-12.md) - Marked S12-37 complete.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The rerun procedure is implemented as a contract; fixture results are not
human agreement evidence.
