# Task Summary: S10-32 — Canonical event validation

**Sprint:** Sprint 10
**Task:** S10-32

## Summary of Work

Added server-owned project/installation binding, event identity/type/reference
checks, timestamp age/skew windows, evidence digest and size checks, duplicate
JSON-key/non-finite-number/depth/field/string limits, actor-hint controls, and
deterministic canonical-body hashing that excludes the relocatable evidence
reference. Adapter-owned fields are validated before evidence is persisted;
evidence failures produce a finite terminal run. Validation produces finite
codes and never includes raw content.

## Files Modified

* [event_validation.py](../../../apps/api/src/projecta_api/connectors/event_validation.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Canonicalization and negative tests included in `7 passed`; Ruff and strict Pyright pass.
