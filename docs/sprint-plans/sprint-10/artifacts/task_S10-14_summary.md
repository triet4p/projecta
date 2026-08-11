# Task Summary: S10-14 — Event inbox and idempotency schema

**Sprint:** Sprint 10
**Task:** S10-14

## Summary of Work

Added the event inbox for stable identity, canonical body hash, evidence reference, project/installation scope, accepted outcome, and bounded conflict metadata. The database identity and conflict target are the contract identity `(project_id, installation_id, event_id)`, so fixture event IDs may safely repeat across projects/installations.

## Files Modified

* [schema.py](../../../apps/api/src/projecta_api/operational/schema.py) and [0001 migration](../../../apps/api/alembic/versions/0001_connector_operational.py) — inbox DDL.
* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py) — atomic claim/replay.
* [test_connector_postgres_integration.py](../../../apps/api/tests/test_connector_postgres_integration.py) — concurrency/replay/conflict evidence.

## Testing

* **Status:** Passed
* **Execution:** Compose PostgreSQL integration — `2 passed`.

## Additional Notes

One concurrent claimant wins; the loser observes `in_progress`. A second project can independently claim the same adapter event ID.
