# Task Summary: S10-35 — Cursor commit semantics

**Sprint:** Sprint 10
**Task:** S10-35

## Summary of Work

The kernel carries the adapter's opaque cursor through the pull result and gives
it to the operational repository only after every new event has completed source
commit. Non-terminal event completions do not advance the cursor; a batch has one
cursor revision update, while replay, validation, conflict, timeout, and source
failure leave the previous cursor unchanged.

## Files Modified

* [orchestration.py](../../../apps/api/src/projecta_api/connectors/orchestration.py)
* [ports.py](../../../apps/api/src/projecta_api/operational/ports.py)
* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py)

## Testing

* **Status:** Passed
* **Execution:** Cursor behavior included in kernel/operational focused suites; `23 passed`.
