# Task Summary: S11-24 — Logout, expiry, and revocation

**Sprint:** Sprint 11
**Task:** S11-24

## Summary of Work
Added local logout revocation and deletion of browser cookies. Session reads reject expiry/revocation and membership is read from the server repository for every principal resolution.

## Files Modified
* [apps/api/src/projecta_api/identity/oidc.py](../../../../apps/api/src/projecta_api/identity/oidc.py)
* [apps/api/src/projecta_api/identity/routes.py](../../../../apps/api/src/projecta_api/identity/routes.py)

## Testing
* **Test File:** [test_sprint11_identity.py](../../../../apps/api/tests/test_sprint11_identity.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_identity.py`

## Additional Notes
Cold restore/session epoch invalidation remains an explicit recovery contract for the following recovery phase.
