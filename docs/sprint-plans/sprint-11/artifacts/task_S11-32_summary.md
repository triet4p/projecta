# Task Summary: S11-32

**Sprint:** Sprint 11
**Task:** S11-32 — Least-privilege workload policy

## Summary of Work

Added a service-level OpenBao policy limited to versioned Projecta connector-secret paths, token self-lookup, and health. Projecta continues to enforce exact installation authorization; administrative, list-all, policy, seal, and arbitrary secret paths are absent.

## Files Modified

* [infra/openbao/policies/projecta-api.hcl](../../../../infra/openbao/policies/projecta-api.hcl) - Least-privilege runtime policy.
* [docs/runbooks/openbao-sprint-11.md](../../../../docs/runbooks/openbao-sprint-11.md) - Custody boundary explanation.

## Testing

* **Test File:** [test_sprint11_openbao_contract.py](../../../../scripts/tests/test_sprint11_openbao_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_openbao_contract.py`

## Additional Notes

Per-installation OpenBao policies are intentionally out of scope; exact scope remains Projecta-owned.
