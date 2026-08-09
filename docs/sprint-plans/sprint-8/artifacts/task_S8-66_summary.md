# Task Summary: S8-66 — Released semantic and application regressions

**Sprint:** Sprint 8
**Task:** S8-66
**Status:** Complete

## Outcome

Added `scripts/run_sprint8_validation.ps1`, a working-directory-aware release
gate for Python, Semantic Core, frontend, API drift, Nginx, UI contract,
implicit-behavior, Compose health, and whitespace validation. Ontology container
validation is an explicit `-RunOntology` mode so a machine without Docker is not
misreported as green.

## Validation

- Python suite: `115 passed, 3 skipped`.
- Semantic Core: `mvn verify` passed.
- Frontend unit/contract suite: `15 passed`.
- Full-repository Python typecheck, frontend typecheck, lint, production build, API drift, Nginx, UI contract,
  implicit-behavior, Compose health, and `git diff --check` passed.
- Full repository `uv run pyright`: 0 errors, 0 warnings.
- Ontology container gate: `-RunOntology` executed successfully with 140/140
  checks passed.
