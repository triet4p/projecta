# Task Summary: S10-36 — Dead-letter capture

**Sprint:** Sprint 10
**Task:** S10-36

## Summary of Work

Terminal connector failures are recorded with only an allowlisted failure code,
bounded safe detail, run/event/install handles, and repository timestamps. The
orchestrator filters codes before persistence and excludes payloads, secrets,
stack traces, SQL, RDF identifiers, and paths.

## Files Modified

* [orchestration.py](../../../apps/api/src/projecta_api/connectors/orchestration.py)
* [contracts.py](../../../apps/api/src/projecta_api/connectors/contracts.py)
* [test_connector_kernel.py](../../../apps/api/tests/test_connector_kernel.py)

## Testing

* **Status:** Passed
* **Execution:** Failure/dead-letter test included in `7 passed`.
