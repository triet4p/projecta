# Task Summary: S12-03 — Rank Priority Business Journeys

**Sprint:** Sprint 12

**Task:** S12-03

## Summary of Work

Ranked eight benchmark journeys from structured capture through untyped
extraction, review, requirement/decision evolution, coordination semantics,
grounded retrieval, safety/isolation, and longitudinal project continuity.
The set stays within the plan's maximum of eight journeys and keeps new
connector/outbound breadth out of scope.

## Files Modified

* [g0-business-scope.md](../g0-business-scope.md) - Ranked journey table and checkpoints.
* [sprint-12.md](../../sprint-12.md) - Marked S12-03 complete.

## Testing

* **Test File:** [test_sprint12_phase_a_contract.py](../../../../scripts/tests/test_sprint12_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_a_contract.py`

## Additional Notes

Each journey must be represented in atomic cases where applicable and in
longitudinal scenarios where temporal state is material.
