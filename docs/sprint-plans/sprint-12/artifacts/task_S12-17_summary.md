# Task Summary: S12-17 — Define Annotation Guidance

**Sprint:** Sprint 12

**Task:** S12-17

## Summary of Work

Defined annotation order, type rules, minimal-span/code-point rules, relation
and link boundaries, abstention/semantic-gap behavior, scenario checkpoints and
required counterexamples.

## Files Modified

* [annotation-guide.v1.md](../../../../evaluation/sprint-12/annotation-guide.v1.md) - Versioned annotation guide.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Guide and G1 binding.
* [sprint-12.md](../../sprint-12.md) - Marked S12-17 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

Guide changes after G3 require a new dataset version and freeze.
