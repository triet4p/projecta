# Task Summary: S11-04 — Benchmark Free OIDC Options

**Sprint:** Sprint 11

**Task:** S11-04

## Summary of Work

Compared self-hosted Keycloak, Entra-backed Projecta login, and retained local
experience/test context across OIDC behavior, Compose/PostgreSQL fit, TLS,
readiness, recovery, operations, migration, and deterministic acceptance.
Keycloak remains a proposal pending G1.

## Files Modified

* [oidc-provider-benchmark.md](../../../architecture/oidc-provider-benchmark.md) - OIDC alternatives and evaluation criteria.
* [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py) - Phase A contract checks.

## Testing

* **Test File:** [test_sprint11_phase_a_contract.py](../../../../scripts/tests/test_sprint11_phase_a_contract.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q scripts/tests/test_sprint11_phase_a_contract.py`

## Additional Notes

G1 selected Keycloak 26.7.0; S11-15 must still record its immutable image
digest and measured resource evidence.
