# Task Summary: S8-61 — Regenerate the Application API client

**Sprint:** Sprint 8
**Task:** S8-61
**Status:** Complete

## Outcome

Regenerated the redacted Sprint 8 Application API snapshot and operation-id
metadata. The public snapshot now includes the structured Note draft/list/detail,
Note import, and candidate edit boundaries while continuing to exclude the
internal context-secret header and internal entity-link path.

- Snapshot remains the compatibility file
  `docs/architecture/application-api.sprint7.openapi.json` and is versioned as
  `s8.0` for continuity with the existing drift tooling.
- `apps/api/scripts/generate_openapi_snapshot.py` merges backend additions,
  normalizes path parameter names, assigns stable public operation IDs, and
  rejects forbidden internal fields.
- The frontend operation metadata now includes the Sprint 8 operations,
  including bounded candidate edit options.

## Validation

- `uv run --project apps/api python apps/api/scripts/generate_openapi_snapshot.py` — passed.
- `node apps/web/scripts/generate-api-client.mjs` — passed.
- `uv run --project apps/api python apps/web/scripts/check-api-contract.py` —
  passed: 39 public paths, no drift.
- Forbidden-field scan — passed.

## Boundary

The generated snapshot documents the browser-facing boundary only. It does not
expose provider credentials, trusted context secrets, graph IRIs, or Semantic
Core internals.
