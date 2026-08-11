# Task Summary: S10-29 — Connector registry

**Sprint:** Sprint 10
**Task:** S10-29

## Summary of Work

Added an explicit registry that resolves only composed, allowlisted adapters,
rejects duplicate and unknown registrations, and exposes bounded descriptor and
capability metadata. The adapter port has no Semantic Core, RDF, browser, or
general filesystem/network dependency.

## Files Modified

* [registry.py](../../../apps/api/src/projecta_api/connectors/registry.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Registry and kernel tests included in `7 passed`; Ruff and strict Pyright pass.
