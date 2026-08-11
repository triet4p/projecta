# Task Summary: S10-27 — Authorization and secret negative tests

**Sprint:** Sprint 10
**Task:** S10-27

## Summary of Work

Added negative coverage for missing/forged principal context, cross-project membership, stale installation and run revisions, disabled installations, insufficient roles, unsupported capabilities/types, missing idempotency keys, cross-project secret binding, unavailable references, and production local-adapter startup. Public mapping is bounded to safe 401/403/404/409/503-style codes and request correlation.

## Files Modified

* [test_connector_authorization.py](../../../apps/api/tests/test_connector_authorization.py) — authorization matrix and safe public problem assertions.
* [test_connector_secrets.py](../../../apps/api/tests/test_connector_secrets.py) — secret leak/scope negatives.
* [authorization.py](../../../apps/api/src/projecta_api/connectors/authorization.py) — finite safe problem mapper.

## Testing

* **Status:** Passed
* **Execution:** C focused suite — `10 passed`; Ruff and strict Pyright pass.

## Additional Notes

No production OIDC/RBAC provider or real external connector was added.
