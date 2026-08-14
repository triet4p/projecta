# Task Summary: S12-23 — Define Dataset Validation Rules

**Sprint:** Sprint 12

**Task:** S12-23

## Summary of Work

Defined fail-closed validation for schemas, IDs, source spans, Unicode
boundaries, released allowlists, same-project references, abstention/gaps,
scenario checkpoints, quotas, annotation, provenance, privacy, leakage and
custody.

## Files Modified

* [g1-dataset-contract.md](../g1-dataset-contract.md) - Deterministic validation rule set.
* [atomic-case.schema.json](../../../../evaluation/sprint-12/schema/atomic-case.schema.json) - Closed-world atomic constraints.
* [scenario-case.schema.json](../../../../evaluation/sprint-12/schema/scenario-case.schema.json) - Closed-world scenario constraints.
* [sprint-12.md](../../sprint-12.md) - Marked S12-23 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Runtime/source payloads are never printed as validation errors.
