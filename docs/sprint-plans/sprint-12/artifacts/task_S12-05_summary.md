# Task Summary: S12-05 — Define Business Outcomes

**Sprint:** Sprint 12

**Task:** S12-05

## Summary of Work

Defined useful, harmful, incomplete and correct-abstention outcomes for every
priority journey. Outcomes cover both semantic behavior and reviewer/business
consequences, including unsafe assertion, evidence loss, temporal collapse,
cross-project disclosure and unsupported answers.

## Files Modified

* [g0-business-scope.md](../g0-business-scope.md) - Outcome matrix for all journeys.
* [sprint-12.md](../../sprint-12.md) - Marked S12-05 complete.

## Testing

* **Test File:** [test_sprint12_phase_a_contract.py](../../../../scripts/tests/test_sprint12_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_a_contract.py`

## Additional Notes

Hard-invariant failures remain blocking even when aggregate business or
semantic metrics look strong.
