# Task Summary: S10-15 — Sync runs, cursors, and dead letters

**Sprint:** Sprint 10
**Task:** S10-15

## Summary of Work

Added run, single-attempt, cursor, dead-letter, and audit tables. Repository operations enforce one terminal run outcome, explicit retry parent linkage, opaque cursor revisions, bounded sanitized failures, and project predicates.

## Files Modified

* [schema.py](../../../apps/api/src/projecta_api/operational/schema.py) and [0001 migration](../../../apps/api/alembic/versions/0001_connector_operational.py) — DDL.
* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py) — typed run/cursor/dead-letter/audit mutations.
* [test_connector_postgres_integration.py](../../../apps/api/tests/test_connector_postgres_integration.py) — terminal/failure evidence.

## Testing

* **Status:** Passed
* **Execution:** PostgreSQL integration — `2 passed`.

## Additional Notes

Failure detail is bounded and provider payloads/stack traces are excluded.
