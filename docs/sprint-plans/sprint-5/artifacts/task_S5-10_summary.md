# Task Summary: S5-10 — Define the prompt package

**Sprint:** Sprint 5
**Task:** S5-10

## Summary of Work

Added stable prompt version `m3.prompt.v1` with explicit no-RDF/no-policy/no-
external-action instructions, server-controlled class/predicate allowlists,
bounded project entity context, exact evidence guidance, abstention behavior,
and delimiters treating note/context content as untrusted data.

## Files Modified

- `apps/api/src/projecta_api/extraction/prompt.py`
- `apps/api/src/projecta_api/extraction/__init__.py`
- `apps/api/tests/test_extraction_prompt.py`

## Testing

- **Command:** `uv run pytest tests/test_extraction_contracts.py tests/test_extraction_prompt.py -q`
- **Coverage:** deterministic ordering, versioning, allowlists, prompt-injection text, and untrusted-data boundaries.
