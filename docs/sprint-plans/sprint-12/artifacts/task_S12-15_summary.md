# Task Summary: S12-15 — Define the Coverage Matrix

**Sprint:** Sprint 12

**Task:** S12-15

## Summary of Work

Defined coverage across all eight G0 journeys, released types and predicates,
languages, source origins, ambiguity, temporal behavior, hostile input,
fabricated links, duplicates, contradictions and Unicode/noisy text.

## Files Modified

* [coverage-matrix.v1.json](../../../../evaluation/sprint-12/coverage-matrix.v1.json) - Versioned coverage matrix.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Coverage acceptance boundary.
* [sprint-12.md](../../sprint-12.md) - Marked S12-15 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Coverage is validated per slice; pooled metrics cannot hide a missing journey or
threat category.
