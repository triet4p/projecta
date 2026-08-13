# Task Summary: S11-10 — Define the OpenBao Operations Proposal

**Sprint:** Sprint 11

**Task:** S11-10

## Summary of Work

Defined the proposed single-instance integrated-Raft topology, TLS and private
management boundary, initialization/manual-unseal custody, least-privilege
workload policy, rotation/revocation, encrypted snapshot/restore, upgrade,
break-glass, and residual-risk workflow.

## Files Modified

* [openbao-operations-proposal.md](../../../architecture/openbao-operations-proposal.md) - OpenBao operations proposal.
* [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py) - Phase A contract checks.

## Testing

* **Test File:** [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_phase_a_contract.py`

## Additional Notes

The approved proposal intentionally makes no HA or unattended-unseal claim.
