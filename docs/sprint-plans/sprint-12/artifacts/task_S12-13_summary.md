# Task Summary: S12-13 — Define the Scenario Gold Schema

**Sprint:** Sprint 12

**Task:** S12-13

## Summary of Work

Defined longitudinal scenario gold for 5–12 ordered events, expected review
decisions, correction classes, temporal effects, source/candidate/asserted/
inferred/provenance checkpoints and grounded competency-question answers.

## Files Modified

* [scenario-case.schema.json](../../../../evaluation/sprint-12/schema/scenario-case.schema.json) - Longitudinal scenario schema.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Scenario acceptance contract.
* [sprint-12.md](../../sprint-12.md) - Marked S12-13 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Scenario gold tests existing lifecycle behavior and does not create a second
semantic read model.
