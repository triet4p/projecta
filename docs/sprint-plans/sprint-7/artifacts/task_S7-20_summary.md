# S7-20 — Credential rotation and removal

Added explicit rotation and removal operations with expected-revision support,
post-commit old-secret cleanup, idempotent removal, and inactive-profile
behavior. No raw secret is returned by either operation.

Validation: repository and settings contracts pass.
