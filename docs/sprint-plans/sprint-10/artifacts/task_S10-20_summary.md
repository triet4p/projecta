# Task Summary: S10-20 — Evidence object-store port

**Sprint:** Sprint 10
**Task:** S10-20

## Summary of Work

Defined the provider-neutral async evidence port and safe request/metadata/receipt types. The port supports bounded content-addressed put, project-scoped head/get streaming, and retention marking without list-all, arbitrary-key, public-URL, or browser-delete operations.

## Files Modified

* [ports.py](../../../apps/api/src/projecta_api/evidence/ports.py) — evidence port and finite errors.
* [local.py](../../../apps/api/src/projecta_api/evidence/local.py) — adapter implementation.

## Testing

* **Status:** Passed
* **Execution:** evidence focused tests — `8 passed`.

## Additional Notes

The v1 allowlist is JSON/text and the maximum object size is 1 MiB.
