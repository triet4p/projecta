# Task Summary: S4-06 — Define the application API contract

**Sprint:** Sprint 4
**Task:** S4-06

## Summary of Work

Defined the FastAPI M2 surface: trusted context, typed capture request,
canonical offset behavior, public errors, capture idempotency, review
orchestration, and current/history/evidence reads.

## Files Modified

- `docs/architecture/application-api.md` — authoritative FastAPI contract.

## Testing

- **Test File:** Not applicable; this is a pre-implementation contract.
- **Status:** Cross-checked with the approved M2 boundary and Semantic Core API;
  released ontology regression passed (73/73).
- **Execution Command:** `docker compose run --build --rm ontology-test`

## Additional Notes

S4-12 through S4-18 implement and test this contract after the ontology
extension is released.
