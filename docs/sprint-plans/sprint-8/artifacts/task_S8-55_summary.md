# Task Summary: S8-55 — Structured Note APIs

**Status:** Complete

Implemented project-scoped draft create/read/update/commit/list and committed
Note list/detail routes. Drafts use SQLite optimistic revisions, opaque handles,
idempotency fingerprints, explicit empty/invalid errors, and server-derived
offsets. Commit marks a draft only after Semantic Core succeeds.

The API client and runtime models are typed; OpenAPI snapshot regeneration is
intentionally reserved for S8-61.
