# Task Summary: S11-31

**Sprint:** Sprint 11
**Task:** S11-31 — Operator initialization and manual-unseal tooling

## Summary of Work

Added explicit operator scripts for Shamir 3-share/2-threshold initialization, safe idempotent rerun behavior, manual unseal, restricted recovery material, and fail-closed status handling. Root and recovery values are never printed or tracked.

## Files Modified

* [scripts/openbao/init.sh](../../../../scripts/openbao/init.sh) - Idempotent operator initialization.
* [scripts/openbao/unseal.sh](../../../../scripts/openbao/unseal.sh) - Two-share manual unseal.
* [docs/runbooks/openbao-sprint-11.md](../../../../docs/runbooks/openbao-sprint-11.md) - Operator procedure and residual risk.

## Testing

* **Test File:** [test_sprint11_openbao_contract.py](../../../../scripts/tests/test_sprint11_openbao_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_openbao_contract.py`

## Additional Notes

Partial initialization material is rejected to avoid accidental overwrite.
