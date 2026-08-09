# Task Summary: S8-60 — Structured Note contract tests

**Status:** Complete

Coverage includes ordering, Unicode/code-point offsets, LF normalization,
empty/duplicate items, closed vocabularies, strict metadata, idempotency
replay/conflict, optimistic concurrency, project-scoped handles, import
abstention, semantic rollback, provenance audit, URL-preserving source detail,
and backward compatibility with raw/segment captures.

Validation evidence:

- API: `112 passed, 3 skipped`.
- Structured Note API/contract tests: `10 passed`.
- Semantic Core: `mvn verify` passed, including SHACL rollback and Unicode
  capture tests.
- Frontend: typecheck, lint, and production build passed.
