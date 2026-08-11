# Task Summary: S10-33 — Single-attempt orchestration

**Sprint:** Sprint 10
**Task:** S10-33

## Summary of Work

Implemented one run per idempotency key, one adapter pull, one absolute deadline,
bounded evidence/source ports, per-event inbox claims, terminal run finishing,
and explicit safe failure mapping. Adapter, evidence, source, and operational
errors do not become hidden success or automatic retries.

## Files Modified

* [orchestration.py](../../../apps/api/src/projecta_api/connectors/orchestration.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Single-attempt kernel test included in `7 passed`; Ruff and strict Pyright pass.
