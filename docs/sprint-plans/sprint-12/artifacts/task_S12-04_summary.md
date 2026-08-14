# Task Summary: S12-04 — Define Target Roles

**Sprint:** Sprint 12

**Task:** S12-04

## Summary of Work

Defined responsibilities and separation of duties for note authors,
coordinators/PMs, technical and business reviewers, tech leads, project
owners, semantic reviewers, annotation/data leads and operators. The contract
prevents case authors, model authors or operators from becoming the sole gold
authority.

## Files Modified

* [g0-business-scope.md](../g0-business-scope.md) - Role and responsibility matrix.
* [sprint-12.md](../../sprint-12.md) - Marked S12-04 complete.

## Testing

* **Test File:** [test_sprint12_phase_a_contract.py](../../../../scripts/tests/test_sprint12_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_a_contract.py`

## Additional Notes

The later G6 reviewer study still requires at least three qualified target-role
reviewers; this task does not claim their availability.
