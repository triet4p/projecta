# Task Summary: S10-37 — Explicit retry

**Sprint:** Sprint 10
**Task:** S10-37

## Summary of Work

Retry requires the policy's connector-admin authorization, the failed parent run
and expected run revision, a new idempotency key, expected installation revision,
and explicit retry lineage. Failed/cancelled event inbox entries can be replayed
only through that visible retry path; no scheduler or recursive retry exists.

## Files Modified

* [orchestration.py](../../../apps/api/src/projecta_api/connectors/orchestration.py)
* [repository.py](../../../apps/api/src/projecta_api/operational/repository.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Explicit failure then retry test included in `7 passed`; authorization suite remains green.
