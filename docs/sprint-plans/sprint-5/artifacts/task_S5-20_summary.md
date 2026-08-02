# Task Summary: S5-20 — Implement relation candidate extraction

**Sprint:** Sprint 5
**Task:** S5-20

## Summary of Work

Added relation normalization for the versioned allowlisted predicates. Each
relation retains its own confidence and exact source evidence, requires both
opaque endpoints in the trusted same-project entity set, rejects self-links,
and fails closed for unknown/cross-project endpoints or invalid evidence.

## Files Modified

- `apps/api/src/projecta_api/extraction/relations.py`
- `apps/api/src/projecta_api/extraction/__init__.py`
- `apps/api/tests/test_relation_extraction.py`

## Testing

- **Command:** `uv run pytest tests/test_relation_extraction.py -q`
- **Coverage:** allowlisted predicate, endpoint isolation, self-relation, and evidence handling.
