# Task Summary: S12-36 — Revise the Annotation Guide

**Sprint:** Sprint 12

**Task:** S12-36

## Summary of Work

Created guide v1.1 with only the two ambiguity rules exposed by the pilot
fixture: ResearchFinding versus ProgressClaim and vague future language that
requires abstention. No ontology, threshold or split rule was changed.

## Files Modified

* [annotation-guide.v1.1.md](../../../../evaluation/sprint-12/pilot/annotation-guide.v1.1.md) - Versioned guide revision.
* [adjudication-log.v1.json](../../../../evaluation/sprint-12/pilot/adjudication-log.v1.json) - Revision rationale.
* [sprint-12.md](../../sprint-12.md) - Marked S12-36 complete.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The revised guide must be tested on a fresh calibration subset before G2
approval.
