# Task Summary: S12-29 — Author the Pilot Atomic Set

**Sprint:** Sprint 12

**Task:** S12-29

## Summary of Work

Authored 20 synthetic atomic cases spanning the released semantic types,
Vietnamese/English/Japanese/mixed text, relation and link examples,
ambiguity, hostile instructions, cross-project isolation, semantic gaps and
noisy input. Every source has a real UTF-8 SHA-256 digest.

## Files Modified

* [atomic-pilot.v1.json](../../../../evaluation/sprint-12/pilot/atomic-pilot.v1.json) - 20-case synthetic pilot.
* [README.md](../../../../evaluation/sprint-12/pilot/README.md) - Pilot status and human-evidence boundary.
* [sprint-12.md](../../sprint-12.md) - Marked S12-29 complete.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

The cases are synthetic calibration fixtures, not customer or human-annotation
evidence.
