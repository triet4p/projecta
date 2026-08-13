# Task Summary: S11-37

**Sprint:** Sprint 11
**Task:** S11-37 — Rotation and revocation tests

## Summary of Work

Tests prove immutable in-flight snapshots, current-version resolution after rotation, fail-closed revocation, sealed/unavailable/unauthorized behavior, and no need for browser or reinstall secret handling.

## Files Modified

* [apps/api/tests/test_sprint11_openbao.py](../../../../apps/api/tests/test_sprint11_openbao.py) - Rotation, snapshot, revocation, and failure tests.
* [docs/runbooks/openbao-sprint-11.md](../../../../docs/runbooks/openbao-sprint-11.md) - Lifecycle and recovery notes.

## Testing

* **Test File:** [test_sprint11_openbao.py](../../../../apps/api/tests/test_sprint11_openbao.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_openbao.py`

## Additional Notes

The snapshot carries the selected version and is immutable for the life of the connector operation.
