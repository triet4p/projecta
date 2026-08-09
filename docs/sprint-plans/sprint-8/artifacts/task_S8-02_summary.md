# Task Summary: No-implicit-fallback contract

**Sprint:** Sprint 8
**Task:** S8-02

## Summary of Work

Defined the fail-explicit runtime contract across Web, Nginx, Application API,
Semantic Core, Fuseki/TDB2, provider adapters, and Compose health boundaries.
The contract distinguishes domain-valid empty results, explicit abstention,
user cancellation, stale state, and operational failure; defines prohibited
implicit provider/project/replay/retry behavior; and establishes mutation,
redaction, readiness, and regression invariants.

## Files Modified

* [fail-explicit-runtime-contract.md](../../../architecture/fail-explicit-runtime-contract.md) - Boundary matrix, state rules, invariants, and regression matrix.
* [sprint-8.md](../sprint-8.md) - Marked S8-02 complete.

## Testing

* **Test File:** N/A; this is a contract artifact.
* **Status:** Passed.
* **Execution Command:** `git diff --check`; reviewed each boundary against the S8-01 evidence inventory and existing M3 error contract.

## Additional Notes

The contract is intentionally `PROPOSAL_ONLY` until S8-11. S8-03 through
S8-06 refine the error taxonomy, event schema, retry policy, and project scope
without weakening the fail-explicit invariants.
