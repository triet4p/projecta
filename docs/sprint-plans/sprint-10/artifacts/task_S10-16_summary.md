# Task Summary: S10-16 — Operational repository ports

**Sprint:** Sprint 10
**Task:** S10-16

## Summary of Work

Defined finite dataclass records and a provider-neutral repository Protocol for installations, event claims/replays/completion, runs, explicit retries, cursors, dead letters, audit, and bounded audit lookup. SQLAlchemy rows do not cross the port.

## Files Modified

* [ports.py](../../../apps/api/src/projecta_api/operational/ports.py) — typed port and records.
* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py) — implementation.
* [test_connector_operational_contract.py](../../../apps/api/tests/test_connector_operational_contract.py) — safety checks.

## Testing

* **Status:** Passed
* **Execution:** Ruff, strict Pyright, focused tests, and PostgreSQL integration.

## Additional Notes

Blocking SQLAlchemy work remains isolated behind the operational boundary.
