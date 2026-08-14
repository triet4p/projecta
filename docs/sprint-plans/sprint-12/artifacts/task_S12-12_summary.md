# Task Summary: S12-12 — Define the Atomic Gold Schema

**Sprint:** Sprint 12

**Task:** S12-12

## Summary of Work

Defined atomic gold for released entity types, relation predicates, bounded
links, exact Unicode evidence spans, abstention and explicit semantic gaps.
The schema rejects arbitrary types, predicates and target identifiers at the
contract boundary.

## Files Modified

* [atomic-case.schema.json](../../../../evaluation/sprint-12/schema/atomic-case.schema.json) - Atomic gold schema.
* [annotation-guide.v1.md](../../../../evaluation/sprint-12/annotation-guide.v1.md) - Labeling decisions and counterexamples.
* [sprint-12.md](../../sprint-12.md) - Marked S12-12 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Unsupported business concepts are represented as semantic gaps, not forced into
the nearest released term.
