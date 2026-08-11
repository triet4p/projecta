# Task Summary: S10-30 — Installation service

**Sprint:** Sprint 10
**Task:** S10-30

## Summary of Work

Implemented policy-checked project-scoped create/read/update/enable/disable
operations with create/update adapter validation, capability snapshots,
revision checks, opaque secret-configured status, and audit records committed
in the same PostgreSQL transaction as each installation mutation. Raw secret
material is never part of the installation snapshot.

## Files Modified

* [installation_service.py](../../../apps/api/src/projecta_api/connectors/installation_service.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Lifecycle test included in `7 passed`; Ruff and strict Pyright pass.
