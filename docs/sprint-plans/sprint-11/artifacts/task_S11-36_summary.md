# Task Summary: S11-36

**Sprint:** Sprint 11
**Task:** S11-36 — Secret readiness and failure semantics

## Summary of Work

Internal statuses distinguish ready, sealed, unavailable, unauthorized, missing, revoked, stale, invalid scope, and rotation conflict. The API readiness surface emits only the finite public `SECRET_MANAGER_UNAVAILABLE` problem and connector policy maps internal errors to safe finite codes.

## Files Modified

* [apps/api/src/projecta_api/secrets/openbao.py](../../../../apps/api/src/projecta_api/secrets/openbao.py) - Internal finite status/error mapping.
* [apps/api/src/projecta_api/connectors/secrets.py](../../../../apps/api/src/projecta_api/connectors/secrets.py) - Safe connector mapping.
* [apps/api/src/projecta_api/main.py](../../../../apps/api/src/projecta_api/main.py) - Readiness gate.

## Testing

* **Test File:** [test_sprint11_openbao.py](../../../../apps/api/tests/test_sprint11_openbao.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_openbao.py`

## Additional Notes

Paths, tokens, provider responses, and plaintext are excluded from public errors.
