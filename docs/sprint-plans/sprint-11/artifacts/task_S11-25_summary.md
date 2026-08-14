# Task Summary: S11-25 — Production principal resolution

**Sprint:** Sprint 11
**Task:** S11-25

## Summary of Work
Added a production connector principal adapter that derives allowed projects and connector roles from the validated Projecta session/membership seam. Production middleware strips browser-supplied actor, project, role, capability, and trusted-context headers.

## Files Modified
* [apps/api/src/projecta_api/connectors/authorization.py](../../../../apps/api/src/projecta_api/connectors/authorization.py)
* [apps/api/src/projecta_api/context.py](../../../../apps/api/src/projecta_api/context.py)
* [apps/api/src/projecta_api/main.py](../../../../apps/api/src/projecta_api/main.py)

## Testing
* **Test File:** [test_sprint11_identity.py](../../../../apps/api/tests/test_sprint11_identity.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_identity.py`

## Additional Notes
The local adapter is still rejected in production.
