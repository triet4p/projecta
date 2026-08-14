# Task Summary: S11-19 — Keycloak readiness and startup ordering

**Sprint:** Sprint 11
**Task:** S11-19

## Summary of Work
Added bounded production OIDC readiness that verifies discovery issuer, JWKS URI, and a non-empty signing-key set before API readiness reports ready. Compose orders Keycloak behind PostgreSQL and the production edge behind API/Keycloak health.

## Files Modified
* [apps/api/src/projecta_api/identity/readiness.py](../../../../apps/api/src/projecta_api/identity/readiness.py)
* [apps/api/src/projecta_api/main.py](../../../../apps/api/src/projecta_api/main.py)
* [compose.prod.yaml](../../../../compose.prod.yaml)

## Testing
* **Test File:** [test_main.py](../../../../apps/api/tests/test_main.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_main.py`

## Additional Notes
Transient OIDC failure returns not-ready; no local fallback is selected.
