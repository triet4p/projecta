# Task Summary: S12-31 — Validate Pilot Source Provenance

**Sprint:** Sprint 12

**Task:** S12-31

## Summary of Work

Validated the atomic sources as synthetic, permission-bound, classified by
language/sensitivity/origin and bound to exact SHA-256 digests. Added and
validated scenario-level `sourceManifest` entries after the original fixture
omitted them.

## Files Modified

* [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py) - Digest, span and provenance checks.
* [atomic-pilot.v1.json](../../../../evaluation/sprint-12/pilot/atomic-pilot.v1.json) - Provenance-bound pilot cases.
* [sprint-12.md](../../sprint-12.md) - Marked S12-31 complete after scenario validation.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

No restricted or external production payload was used; qualified human
annotation evidence is still pending for G2.
