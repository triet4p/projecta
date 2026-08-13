# Task Summary: S11-40

**Sprint:** Sprint 11
**Task:** S11-40 — Typed Teams installation configuration

## Summary of Work

Added an internal, finite Teams installation binding for exactly one tenant, team, and channel, with scoped secret reference, additive inbound capability, bounded sync/reply limits, and revision binding. Provider identifiers remain internal installation configuration.

## Files Modified

* [apps/api/src/projecta_api/connectors/teams.py](../../../../apps/api/src/projecta_api/connectors/teams.py) - Typed binding and safe internal projection.
* [apps/api/src/projecta_api/connectors/contracts.py](../../../../apps/api/src/projecta_api/connectors/contracts.py) - Teams connector type and provider config seam.
* [apps/api/src/projecta_api/connectors/installation_service.py](../../../../apps/api/src/projecta_api/connectors/installation_service.py) - Provider config lifecycle persistence.

## Testing

* **Test File:** [test_sprint11_teams_adapter.py](../../../../apps/api/tests/test_sprint11_teams_adapter.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_teams_adapter.py`

## Additional Notes

Public Teams setup DTOs remain deferred to S11-51 and later.
