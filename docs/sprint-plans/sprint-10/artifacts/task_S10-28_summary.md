# Task Summary: S10-28 — Typed connector contracts

**Sprint:** Sprint 10
**Task:** S10-28

## Summary of Work

Added finite Pydantic contracts for descriptors/capabilities, installations,
opaque cursors, canonical events, pull commands/results, sync commands,
retry lineage, bounded outcomes, and sanitized connector errors. Unknown fields,
unsafe identifiers, timestamps without timezone, invalid hashes, and sensitive
error details fail closed.

## Files Modified

* [contracts.py](../../../apps/api/src/projecta_api/connectors/contracts.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Kernel focused suite — `7 passed`; Ruff and strict Pyright pass.
