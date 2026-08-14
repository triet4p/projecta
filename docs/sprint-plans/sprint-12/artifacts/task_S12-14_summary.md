# Task Summary: S12-14 — Define the Correction Taxonomy

**Sprint:** Sprint 12

**Task:** S12-14

## Summary of Work

Defined the correction taxonomy: `unchanged`, `formatting-only`,
`minor-semantic`, `major-semantic`, `rejected`, `missing-output` and
`not-applicable`, with review disposition kept separate from correction
severity.

## Files Modified

* [annotation-guide.v1.md](../../../../evaluation/sprint-12/annotation-guide.v1.md) - Correction and review rules.
* [scenario-case.schema.json](../../../../evaluation/sprint-12/schema/scenario-case.schema.json) - Correction enum.
* [sprint-12.md](../../sprint-12.md) - Marked S12-14 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

The taxonomy measures reviewer effort and does not prescribe subjective timing.
