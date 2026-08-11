# Task Summary: S10-34 — Explicit replay semantics

**Sprint:** Sprint 10
**Task:** S10-34

## Summary of Work

Reusing a completed operation idempotency key returns a replay result without a
second adapter call or source commit. The operational repository preserves the
canonical body conflict boundary and allows failed/cancelled inbox entries to be
re-entered only by an explicit retry path.

## Files Modified

* [orchestration.py](../../../apps/api/src/projecta_api/connectors/orchestration.py)
* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Replay/failure-reentry coverage included in `7 passed`; focused operational suite `23 passed`.
