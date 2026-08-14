# Task Summary: S12-11 — Define the Case Envelope

**Sprint:** Sprint 12

**Task:** S12-11

## Summary of Work

Defined closed-world atomic and scenario envelopes with stable IDs, schema
versions, canonical source text, origin, language, sensitivity, license,
permission reference, content digest, split and scenario lineage.

## Files Modified

* [atomic-case.schema.json](../../../../evaluation/sprint-12/schema/atomic-case.schema.json) - Atomic case envelope.
* [scenario-case.schema.json](../../../../evaluation/sprint-12/schema/scenario-case.schema.json) - Scenario envelope.
* [g1-dataset-contract.md](../g1-dataset-contract.md) - Contract and split summary.
* [sprint-12.md](../../sprint-12.md) - Marked S12-11 complete.

## Testing

* **Test File:** [test_sprint12_phase_b_contract.py](../../../../scripts/tests/test_sprint12_phase_b_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_b_contract.py`

## Additional Notes

The schemas are contracts only; no held-out payload is committed.
