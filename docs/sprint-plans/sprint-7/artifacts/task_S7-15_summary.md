# S7-15 — Operational persistence baseline

Implemented a SQLite operational database with idempotent schema creation for
encrypted secret records, project-scoped LLM profiles, migrations, and
configuration audit rows. Added the Compose-backed operational volume and
deployment path configuration.

Validation: API tests, Ruff, and Pyright pass.
