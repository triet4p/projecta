# Task Summary: S12-30 — Draft the Pilot Scenario Set

**Sprint:** Sprint 12

**Task:** S12-30

## Summary of Work

Drafted three five-event synthetic episodes covering requirement/decision change,
coordination semantics and ambiguity/hostility/isolation. The first draft
omitted the schema-required `sourceManifest`; the field was added and the
instances are now checked against the approved schema contract.

## Files Modified

* [scenario-pilot.v1.json](../../../../evaluation/sprint-12/pilot/scenario-pilot.v1.json) - Three longitudinal pilot episodes.
* [g2-annotation-pilot.md](../g2-annotation-pilot.md) - Pilot acceptance evidence.
* [sprint-12.md](../../sprint-12.md) - Marked S12-30 complete after validation.

## Testing

* **Test File:** [test_sprint12_phase_c_contract.py](../../../../scripts/tests/test_sprint12_phase_c_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint12_phase_c_contract.py`

## Additional Notes

Scenario fixtures exercise lifecycle checkpoints but do not imply a production
dataset or human reviewer study. The repaired manifest is checked by the Phase
C contract test.
