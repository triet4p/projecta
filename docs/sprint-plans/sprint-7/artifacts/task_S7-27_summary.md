# S7-27 — Typed Application API client

Added typed models and client helpers for released M2–M4 operations and the
implemented settings boundary. Requests carry generated correlation IDs and
mutation idempotency keys; non-success responses become sanitized RFC 7807
`ApiError` values. A deterministic generator compares committed operation IDs
to the Sprint 7 OpenAPI snapshot.

Validation: API drift check and client unit tests pass.
