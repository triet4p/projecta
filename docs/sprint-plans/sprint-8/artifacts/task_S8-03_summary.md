# Task Summary: Finite error taxonomy

**Sprint:** Sprint 8
**Task:** S8-03

## Summary of Work

Defined a closed Sprint 8 error taxonomy with stable public problem codes,
HTTP status, normalized internal boundary classes, retryability, terminal
outcomes, mutation rules, mapping ownership, compatibility treatment for the
released `SEMANTIC_CONTRACT_UNAVAILABLE` code, and an explicit redaction
contract. Added regression requirements for provider, Core, Fuseki, SHACL,
scope, idempotency, and unexpected failures.

## Files Modified

* [error-taxonomy.md](../../../architecture/error-taxonomy.md) - Public/internal error vocabulary and mapping rules.
* [sprint-8.md](../sprint-8.md) - Marked S8-03 complete.

## Testing

* **Test File:** N/A; this is a contract artifact.
* **Status:** Passed.
* **Execution Command:** `git diff --check`; cross-checked public compatibility codes against `docs/architecture/application-api.md` and M3 extraction classes against `docs/architecture/llm-extraction-errors.md`.

## Additional Notes

The new vocabulary is proposal-only until G1. The existing public envelope and
compatibility alias are retained so S8-03 does not silently release an API
breaking change.
