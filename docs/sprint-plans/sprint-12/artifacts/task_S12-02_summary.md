# Task Summary: S12-02 — Define the Buyer-facing Hypothesis

**Sprint:** Sprint 12

**Task:** S12-02

## Summary of Work

Defined the buyer-facing hypothesis that Projecta should reduce the effort of
turning fragmented project notes into traceable knowledge while preserving
human review, evidence, provenance and project isolation. Added measurable
conditions for semantic correctness, review effort, grounded answers and
reproducibility without making a universal AI claim.

## Files Modified

* [g0-business-scope.md](../g0-business-scope.md) - Hypothesis and evidence conditions.
* [sprint-12.md](../../sprint-12.md) - Marked S12-02 complete.

## Testing

* **Test File:** [test_sprint12_phase_a_contract.py](../../../../scripts/tests/test_sprint12_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_a_contract.py`

## Additional Notes

Business utility, semantic quality, safety and operational metrics remain
separate dimensions; no single pooled score is authorized.
