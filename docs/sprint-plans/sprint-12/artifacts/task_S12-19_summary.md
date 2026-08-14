# Task Summary: S12-19 — Define Provenance and Licensing Policy

**Sprint:** Sprint 12

**Task:** S12-19

## Summary of Work

Defined required case origin, permission/license reference, authoring metadata,
content digest, annotation provenance and model-assisted origin labeling.
Prohibited the use of provider output as a substitute for permission or
human-authored provenance.

## Files Modified

* [data-governance.v1.md](../../../../evaluation/sprint-12/data-governance.v1.md) - Provenance and licensing policy.
* [atomic-case.schema.json](../../../../evaluation/sprint-12/schema/atomic-case.schema.json) - Required source provenance fields.
* [sprint-12.md](../../sprint-12.md) - Marked S12-19 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

No external or work-tenant data was acquired.
