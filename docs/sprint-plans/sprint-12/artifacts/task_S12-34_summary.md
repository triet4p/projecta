# Task Summary: S12-34 — Measure Pilot Agreement

**Sprint:** Sprint 12

**Task:** S12-34

## Summary of Work

Produced a deterministic fixture agreement report for type/abstention, spans
and relation/link, with metrics recomputed from the bound labels. The span F1
is 36/37 (0.97297); scenario graph-state and competency-question agreement
are not evaluated because no independent labels exist. S12-34 is reopened for
the human measurement.

## Files Modified

* [agreement-report.v1.json](../../../../evaluation/sprint-12/pilot/agreement-report.v1.json) - Fixture agreement metrics and thresholds.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - Provisional results and interpretation.
* [sprint-12.md](../../sprint-12.md) - Reopened S12-34 pending human metrics.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

Fixture agreement is diagnostic only and cannot satisfy G2 human reliability
approval.
