# Task Summary: S5-21 — Implement output normalization and validation

**Sprint:** Sprint 5
**Task:** S5-21

## Summary of Work

Added the atomic normalization pipeline that validates entity evidence,
relation predicates/endpoints/evidence, and bounded links before returning any
result. It recomputes source evidence, rejects mention mismatches, removes
duplicates using canonical identity keys, and orders entity/relation/link
outputs deterministically. Any failure raises a normalized error before
persistence is called.

## Files Modified

- `apps/api/src/projecta_api/extraction/normalize.py`
- `apps/api/src/projecta_api/extraction/links.py`
- `apps/api/src/projecta_api/extraction/__init__.py`
- `apps/api/tests/test_extraction_normalization.py`

## Testing

- **Command:** `uv run pytest tests/test_extraction_normalization.py -q`
- **Coverage:** all-category validation, duplicate elimination, deterministic ordering, and pre-persistence failure boundary.
