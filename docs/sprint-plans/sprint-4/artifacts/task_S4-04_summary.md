# Task Summary: S4-04 — Resolve the semantic gap

**Sprint:** Sprint 4
**Task:** S4-04

## Summary of Work

Prepared a complete `PROPOSAL_ONLY` ontology review packet for canonical Note
text and exact NoteItem evidence offsets. The proposal defines alternatives,
semantic commitments, SHACL behavior, compatibility impact, validation plan,
and human decisions; it does not edit released ontology artifacts.

## Files Modified

- `docs/ontology/quick-note-evidence-offsets-proposal.md` — governed semantic proposal.

## Testing

- **Test File:** `scripts/validate_ontology.py`
- **Status:** Existing ontology regression passed (73/73); proposed terms are
  intentionally not present in the released suite.
- **Execution Command:** `docker compose run --build --rm ontology-test`

## Additional Notes

Human approval is required for semantic meaning, vocabulary, validation
behavior, and authorization to draft implementation. Dependent implementation
tasks remain blocked at S4-05.
