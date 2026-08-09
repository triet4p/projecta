# S8-29 summary

Added typed Application API contracts for project list/read/select and
overview. The public boundary maps internal project identifiers to stable
opaque handles, bounds list limits to 100, returns a typed empty collection
only for a healthy configured domain, and maps catalog/not-found/stale errors
to finite problem codes. The OpenAPI snapshot and frontend contract metadata
were updated; direct Core headers and identifiers remain private.

Validation:

- `uv run --project apps/api pytest -q apps/api/tests/test_project_workspace.py`
  passed.
- `npm run check:api-drift` passed with 19 public paths.
- Ruff checks passed after formatting.
