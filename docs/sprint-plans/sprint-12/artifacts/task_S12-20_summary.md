# Task Summary: S12-20 — Define Privacy and Retention Policy

**Sprint:** Sprint 12

**Task:** S12-20

## Summary of Work

Defined synthetic/de-identified data boundaries, prohibited payload classes,
authorization and deletion requirements, repository sanitization, test custody,
retention ownership and breach-response behavior.

## Files Modified

* [data-governance.v1.md](../../../../evaluation/sprint-12/data-governance.v1.md) - Privacy, retention and deletion rules.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - G1 validation failures for prohibited data.
* [sprint-12.md](../../sprint-12.md) - Marked S12-20 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

An exposure or withdrawal invalidates affected manifests and results; cases may
not be silently replaced.
