# Task Summary: Explicit retry contract

**Sprint:** Sprint 8
**Task:** S8-05

## Summary of Work

Decided that interactive extraction is single-attempt by default and that
retries require an explicit user action, reviewed evaluation/recovery mode, or
health-probe scheduler. Defined retry authorization, eligible error classes,
attempt budgets, idempotency behavior, provider configuration immutability,
replay isolation, timeout budgets, and regression requirements. Preserved the
approved Sprint 5 evaluation-only `invalid_evidence` retry as a non-product
exception.

## Files Modified

* [explicit-retry-contract.md](../../../architecture/explicit-retry-contract.md) - Retry modes and safeguards.
* [sprint-8.md](../sprint-8.md) - Marked S8-05 complete.

## Testing

* **Test File:** N/A; this is a policy/contract artifact.
* **Status:** Passed.
* **Execution Command:** `git diff --check`; cross-checked `ResilientGateway`, extraction composition, replay adapter, and the approved Sprint 5 evaluation exception.

## Additional Notes

S8-14 must make the current retry helper mode-aware before changing the
interactive runtime. This task does not itself modify runtime code.
