# Task Summary: S12-31 — Validate Pilot Source Provenance

**Sprint:** Sprint 12

**Task:** S12-31

## Summary of Work

Validated that every pilot source is synthetic, permission-bound, classified by
language/sensitivity/origin and bound to the exact SHA-256 digest of its UTF-8
source text. Evidence spans are checked against the source string.

## Files Modified

* [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py) - Digest, span and provenance checks.
* [atomic-pilot.v1.json](../../../../evaluation/sprint-12/pilot/atomic-pilot.v1.json) - Provenance-bound pilot cases.
* [sprint-12.md](../../sprint-12.md) - Marked S12-31 complete.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

No restricted or external production payload was used.
