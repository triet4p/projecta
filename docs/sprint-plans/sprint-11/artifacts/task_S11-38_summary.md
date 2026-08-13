# Task Summary: S11-38

**Sprint:** Sprint 11
**Task:** S11-38 — OpenBao snapshot and restore tooling

## Summary of Work

Added operator snapshot and restore scripts using encrypted temporary Raft snapshots, SHA-256 integrity verification, off-host locations, explicit contract-version matching, plaintext cleanup, and manual-unseal/workload-reauthentication guidance.

## Files Modified

* [scripts/openbao/snapshot.sh](../../../../scripts/openbao/snapshot.sh) - Encrypted snapshot and integrity record.
* [scripts/openbao/restore.sh](../../../../scripts/openbao/restore.sh) - Isolated restore and version guard.
* [docs/runbooks/openbao-sprint-11.md](../../../../docs/runbooks/openbao-sprint-11.md) - RPO/RTO and restore procedure.

## Testing

* **Test File:** [test_sprint11_openbao_contract.py](../../../../scripts/tests/test_sprint11_openbao_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_openbao_contract.py`

## Additional Notes

Projecta sessions are not restored by this task; later recovery must invalidate the session epoch.
