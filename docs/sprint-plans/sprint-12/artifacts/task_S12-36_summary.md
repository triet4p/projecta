# Task Summary: S12-36 — Revise the Annotation Guide

**Sprint:** Sprint 12

**Task:** S12-36

## Summary of Work

Accepted guide v1.1 for the synthetic AI-reviewed track and aligned the pilot
gold with AG-01, minimal link spans and released supersession semantics. No
ontology, threshold or split rule was changed.

## Files Modified

* [annotation-guide.v1.1.md](../../../../evaluation/sprint-12/pilot/annotation-guide.v1.1.md) - Versioned guide revision.
* [adjudication-log.v1.json](../../../../evaluation/sprint-12/pilot/adjudication-log.v1.json) - Revision rationale.
* [sprint-12.md](../../sprint-12.md) - Recorded guide completion under the amendment.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The revised guide is bound to the disjoint fresh-rerun artifact from S12-37.
