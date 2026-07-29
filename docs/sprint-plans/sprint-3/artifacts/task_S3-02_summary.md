# Task Summary: S3-02 — Define the domain-safe API contract

**Sprint:** Sprint 3
**Task:** S3-02

## Summary of Work

Defined the framework-neutral internal HTTP contract for validation,
confirmation, rejection, and three project-scoped allowlisted query views. The
contract binds trusted project context server-side, prohibits raw SPARQL and
graph IRIs, specifies problem responses, and defines idempotent terminal
decision behavior.

## Files Modified

- [docs/architecture/semantic-core-api.md](../../../../docs/architecture/semantic-core-api.md) - API boundary, schemas, errors, and HTTP semantics.
- [docs/sprint-plans/sprint-3.md](../../../../docs/sprint-plans/sprint-3.md) - records task completion.

## Testing

- **Test Type:** Documentation review; executable API-schema tests are scheduled in S3-16 after service scaffolding.
- **Validation Performed:** Checked alignment with S3-01 graph-mutation boundary, released v0.2 lifecycle queries, and the project-isolation guardrail.
- **Status:** Ready for S3-03 human contract review.

## Additional Notes

- The physical idempotency store is deliberately undecided. It is operational
  state and must be proven atomic with the terminal decision in S3-13/S3-14.
