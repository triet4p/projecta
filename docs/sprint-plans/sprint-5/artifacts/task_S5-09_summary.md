# Task Summary: S5-09 — Define the versioned extraction contract

**Sprint:** Sprint 5
**Task:** S5-09

## Summary of Work

Added the `m3.v1` strict Pydantic contract for entity, relation, evidence,
confidence, entity-link, usage, and abstention outputs. Types and predicates
are allowlisted, IDs are opaque URL-safe values rather than RDF/IRI fields,
extra provider payload fields are rejected, evidence ranges are half-open, and
abstention cannot coexist with candidates.

## Files Modified

- `apps/api/src/projecta_api/extraction/contracts.py`
- `apps/api/src/projecta_api/extraction/__init__.py`
- `apps/api/tests/test_extraction_contracts.py`

## Testing

- **Command:** `uv run pytest tests/test_extraction_contracts.py -q`
- **Expected coverage:** accepted aliases, allowlist rejection, arbitrary IRI rejection, extra-field rejection, and explicit abstention.
