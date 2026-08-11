# Task Summary: S10-49 — Connections screen

Added a workspace-scoped Connections screen for catalog, JSON/Mock setup,
installation state, enable/disable, explicit sync, retry, and last-run summary.
The screen uses the existing shell and never renders credentials or internal IDs.

Testing: TypeScript, lint, Vitest, production build, and deterministic Playwright
test source added; browser execution awaits the locally missing Playwright binary.
