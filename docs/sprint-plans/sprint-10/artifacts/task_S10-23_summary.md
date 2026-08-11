# Task Summary: S10-23 — Connector-principal port

**Sprint:** Sprint 10
**Task:** S10-23

## Summary of Work

Added a provider-neutral principal port with finite actions, roles, capabilities, server-owned allowed-project scope, auth source, and request/operation correlation. The port accepts only a trusted actor context and never treats browser project/actor values as authority.

## Files Modified

* [authorization.py](../../../apps/api/src/projecta_api/connectors/authorization.py) — principal request/record/port.
* [test_connector_authorization.py](../../../apps/api/tests/test_connector_authorization.py) — correlation, forged actor, and scope tests.

## Testing

* **Status:** Passed
* **Execution:** `uv run pytest -q tests/test_connector_authorization.py` — `6 passed` within the C focused suite.

## Additional Notes

Production authentication providers are intentionally not introduced.
