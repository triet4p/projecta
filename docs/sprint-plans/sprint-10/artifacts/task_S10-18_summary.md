# Task Summary: S10-18 — Atomic event claim and cursor completion

**Sprint:** Sprint 10
**Task:** S10-18

## Summary of Work

Added project-scoped conflict-safe PostgreSQL claims, replay of the committed outcome, body-hash conflicts, and a transaction that commits an accepted event with its cursor revision. Failed completion records terminal failure without advancing the cursor; persisted run summaries remain truthful after refresh/restart.

## Files Modified

* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py) — claim/completion protocol.
* [test_connector_postgres_integration.py](../../../apps/api/tests/test_connector_postgres_integration.py) — concurrency/replay/conflict/rollback assertions.

## Testing

* **Status:** Passed
* **Execution:** Compose operational integration — `2 passed`.

## Additional Notes

Cross-store Semantic Core completion remains the caller’s explicit prerequisite.
