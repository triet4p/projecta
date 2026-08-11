# Task Summary: S10-24 — Local experience principal adapter

**Sprint:** Sprint 10
**Task:** S10-24

## Summary of Work

Adapted the existing server-owned experience actor/project catalog to the
connector principal port. Local connector-admin capability is opt-in through
`PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED`; a deterministic test adapter is
explicitly separate. Production construction fails closed.

## Files Modified

* [authorization.py](../../../apps/api/src/projecta_api/connectors/authorization.py) — local/test adapters.
* [config.py](../../../apps/api/src/projecta_api/config.py) and [startup.py](../../../apps/api/src/projecta_api/startup.py) — explicit local-admin setting and production readiness rejection.
* [compose.yaml](../../../compose.yaml) — deployment env wiring.
* [test_connector_secrets.py](../../../apps/api/tests/test_connector_secrets.py) — production startup negative tests.

## Testing

* **Status:** Passed
* **Execution:** C focused suite — `10 passed`.

## Additional Notes

Local success remains deterministic test evidence, not production identity readiness.
