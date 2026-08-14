# Task Summary: S12-36 — Revise the Annotation Guide

**Sprint:** Sprint 12

**Task:** S12-36

## Summary of Work

Prepared guide v1.1 with two ambiguity rules exposed by the pilot fixture.
The accepted gold is now consistent with AG-01, but the guide still requires
human review and a fresh rerun, so S12-36 is reopened. No ontology, threshold
or split rule was changed.

## Files Modified

* [annotation-guide.v1.1.md](../../../../evaluation/sprint-12/pilot/annotation-guide.v1.1.md) - Versioned guide revision.
* [adjudication-log.v1.json](../../../../evaluation/sprint-12/pilot/adjudication-log.v1.json) - Revision rationale.
* [sprint-12.md](../../sprint-12.md) - Reopened S12-36 pending review.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The revised guide must be tested on a fresh calibration subset before G2
approval.
