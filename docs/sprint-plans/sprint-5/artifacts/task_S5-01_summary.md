# Task Summary: S5-01 — Fix the executable M3 boundary

**Sprint:** Sprint 5
**Task:** S5-01

## Summary of Work

Defined the executable M3 boundary from an untyped Quick Note to normalized,
project-scoped, reviewable entity/relation/link candidates. The contract now
specifies request/result shapes, bounded entity context, graph effects,
provider-neutral extraction, exact Unicode evidence, idempotency, atomicity,
failure behavior, latency/cost limits, and an end-to-end acceptance scenario.

## Files Modified

- `docs/use-cases/llm-candidate-extraction.md` — M3 executable use case.

## Testing

- **Test File:** Not applicable; this task establishes a use-case contract.
- **Status:** `git diff --check` passed.
- **Execution Command:** `git -c safe.directory=F:/ai-ml/projecta diff --check`

## Additional Notes

This contract does not authorize new ontology terms or provider dependencies.
Those remain subject to the Sprint 5 semantic and technology gates described in
the Sprint Plan.
