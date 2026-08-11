# Task Summary: S10-12 — Deterministic operational migrations

**Sprint:** Sprint 10
**Task:** S10-12

## Summary of Work

Added Alembic metadata, a versioned first migration, standalone `upgrade` entry point, PostgreSQL advisory-lock serialization, explicit nonzero failures, and a documented forward-only rollback boundary. API replicas wait for the one-shot `connector-migrate` service.

## Files Modified

* [alembic.ini](../../../apps/api/alembic.ini), [alembic/env.py](../../../apps/api/alembic/env.py), and [0001 migration](../../../apps/api/alembic/versions/0001_connector_operational.py) — migration implementation.
* [migrate.py](../../../apps/api/src/projecta_api/operational/migrate.py) — fail-explicit runner.
* [connector-migrations.md](../../../architecture/connector-migrations.md) — rollback/deployment boundary.
* [Dockerfile](../../../apps/api/Dockerfile) and [compose.yaml](../../../compose.yaml) — ship/run migration separately.

## Testing

* **Status:** Passed
* **Execution:** Compose migration bootstrap and repeated migration; migration contract tests.

## Additional Notes

Destructive downgrade remains an operator recovery/forward-fix action.
