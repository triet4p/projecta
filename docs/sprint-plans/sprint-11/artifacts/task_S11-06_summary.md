# Task Summary: S11-06 — Define Project Membership and Capability Policy

**Sprint:** Sprint 11

**Task:** S11-06

## Summary of Work

Defined server-owned PostgreSQL membership, the finite `project-reader`,
`reviewer`, and `connector-admin` roles, capability mapping, revision checks,
safe isolation behavior, and a minimal operator seed workflow without generic
ABAC or tenant administration.

## Files Modified

* [project-membership-capability-policy.md](../../../architecture/project-membership-capability-policy.md) - Draft membership and capability contract.
* [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py) - Phase A contract checks.

## Testing

* **Test File:** [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_phase_a_contract.py`

## Additional Notes

Provider claims remain inputs; server membership remains authoritative.
