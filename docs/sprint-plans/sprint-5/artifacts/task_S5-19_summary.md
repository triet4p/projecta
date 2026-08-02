# Task Summary: S5-19 — Implement entity-link proposal

**Sprint:** Sprint 5
**Task:** S5-19

## Summary of Work

Added link normalization that recomputes exact source evidence and retains a
proposal only when its opaque target ID is present in the bounded same-project
entity context from S5-17. Fabricated, unavailable, or cross-project targets
fail closed before persistence; empty/abstention output remains a valid zero-
link path.

## Files Modified

- `apps/api/src/projecta_api/extraction/links.py`
- `apps/api/src/projecta_api/extraction/__init__.py`
- `apps/api/tests/test_entity_links.py`

## Testing

- **Command:** `uv run pytest tests/test_entity_links.py -q`
- **Coverage:** bounded target acceptance, fabricated/cross-project rejection, exact evidence, and abstention.
