# Task Summary: S5-18 — Implement typed entity extraction

**Sprint:** Sprint 5
**Task:** S5-18

## Summary of Work

Added deterministic entity normalization from `m3.v1` output. Entity types are
already allowlisted by Pydantic; this layer recomputes the half-open evidence
substring from immutable source text using Unicode code points and rejects any
out-of-bounds or mismatched item before persistence.

## Files Modified

- `apps/api/src/projecta_api/extraction/entities.py`
- `apps/api/src/projecta_api/extraction/__init__.py`
- `apps/api/tests/test_entity_extraction.py`

## Testing

- **Command:** `uv run pytest tests/test_entity_extraction.py -q`
- **Coverage:** emoji/Unicode code-point evidence and fail-closed mismatch handling.
