# Task Summary: S11-35

**Sprint:** Sprint 11
**Task:** S11-35 — Installation-to-secret scope binding

## Summary of Work

Connector secret resolution now derives project, installation, connector type, provider tenant, and current installation revision before every scoped lookup. Installation records preserve the provider tenant field and cross-scope references resolve as missing.

## Files Modified

* [apps/api/src/projecta_api/connectors/secrets.py](../../../../apps/api/src/projecta_api/connectors/secrets.py) - Exact scope derivation and binding.
* [apps/api/src/projecta_api/connectors/installation_service.py](../../../../apps/api/src/projecta_api/connectors/installation_service.py) - Provider-tenant persistence.
* [apps/api/tests/test_sprint11_openbao.py](../../../../apps/api/tests/test_sprint11_openbao.py) - Cross-scope and policy tests.

## Testing

* **Test File:** [test_sprint11_openbao.py](../../../../apps/api/tests/test_sprint11_openbao.py)
* **Status:** Passed
* **Execution Command:** `uv run --project apps/api pytest -q apps/api/tests/test_sprint11_openbao.py apps/api/tests/test_connector_secrets.py`

## Additional Notes

OpenBao remains a service-level custody boundary rather than an installation authorization engine.
