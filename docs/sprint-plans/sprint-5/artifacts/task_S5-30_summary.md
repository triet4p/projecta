# S5-30 — Canonical Sprint 5 test entry point

Implemented `scripts/run_sprint5.ps1` as the ordered Sprint 5 entry point. It runs the API suite, deterministic replay evaluation, optional live evaluation, and the existing ephemeral Compose system-test workflow. `-SkipCompose` and explicit `-RunLive` support environments without Docker or provider credentials while preserving the same offline checks.

The script does not manufacture credentials and requires the documented environment contract: `PROJECTA_LLM_TYPE`, `PROJECTA_LLM_BASE_URL`, `PROJECTA_LLM_API_KEY`, and `PROJECTA_LLM_MODEL`.
