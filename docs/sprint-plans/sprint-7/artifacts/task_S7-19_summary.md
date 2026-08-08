# S7-19 — Settings write API

Added `PUT /v1/settings/llm` with provider allowlist, URL safety, model
validation, secret-first commit, rollback cleanup, and sanitized problem
responses. Existing active profiles remain intact when validation or storage
fails.

Validation: API suite passes with fail-closed configuration behavior.
