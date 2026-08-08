# S7-35 — Experience diagnostics panel

Added liveness and Semantic Core readiness status, sanitized error/request-ID
surfaces, refresh behavior, and an experience-only inference rebuild control.
The panel explicitly remains separate from production administration.

Validation: `/health/ready`, frontend typecheck, lint, tests, and build pass.
