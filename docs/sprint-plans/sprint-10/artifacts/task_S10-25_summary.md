# Task Summary: S10-25 — Connector policy checks

**Sprint:** Sprint 10
**Task:** S10-25

## Summary of Work

Implemented independent catalog, installation collection/detail, run collection/detail, enable/disable, dead-letter read, and retry policy decisions. Every public catalog/list/read route now invokes the policy. Checks include project membership, finite connector/capability allowlists, admin role, enabled lifecycle, installation revision, run terminal/revision state, and fresh idempotency keys.

## Files Modified

* [authorization.py](../../../apps/api/src/projecta_api/connectors/authorization.py) — policy service and safe problem mapping.
* [test_connector_authorization.py](../../../apps/api/tests/test_connector_authorization.py) — positive/negative matrix.
* [operational/ports.py](../../../apps/api/src/projecta_api/operational/ports.py) and [repository.py](../../../apps/api/src/projecta_api/operational/repository.py) — run revision lookup needed by retry policy.

## Testing

* **Status:** Passed
* **Execution:** C focused suite — `10 passed`; PostgreSQL integration — `2 passed`.

## Additional Notes

Policy errors contain only finite codes/details and no installation, run, or project identifiers.
