# Task Summary: S5-25 — Add Python unit and contract tests

**Sprint:** Sprint 5
**Task:** S5-25

## Summary of Work

Completed focused Python coverage across versioned schemas, gateway/replay/live
adapter boundaries, prompt injection, Unicode evidence, allowlists, bounded
link/relation scope, normalization, retry/error mapping, telemetry redaction,
and orchestration. Added an explicit no-persistence-on-invalid-evidence test.

## Files Modified

- `apps/api/tests/test_sprint5_contract_regressions.py`
- Existing S5-focused test modules under `apps/api/tests/` provide the remaining contract coverage.

## Testing

- **Command:** `uv run pytest -q`
- **Scope:** all configured Python API tests; live provider tests remain mocked/replay-based.
