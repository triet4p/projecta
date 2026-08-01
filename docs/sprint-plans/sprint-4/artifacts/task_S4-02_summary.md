# Task Summary: S4-02 — Define M2 competency questions

**Sprint:** Sprint 4
**Task:** S4-02

## Summary of Work

Defined the M2 questions for source capture, exact segment evidence, candidate
creation, review state, asserted outcomes, provenance, idempotency, and project
isolation. Inference output is explicitly excluded from acceptance.

## Files Modified

- `ontology/competency-questions/quick-note-m2.md` — M2 competency-question set.

## Testing

- **Test File:** Not applicable; two evidence-range questions await a governed
  ontology release before executable SPARQL tests can be added.
- **Status:** Traceability cross-checked against released v0.2 query surfaces;
  released ontology regression passed (73/73).
- **Execution Command:** `docker compose run --build --rm ontology-test`

## Additional Notes

CQ-M2-SRC-002 and CQ-M2-CAND-002 deliberately remain pending until the S4-04
proposal is approved and implemented.
