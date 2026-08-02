# Task Summary: S5-14 — Implement the deterministic replay adapter

**Sprint:** Sprint 5
**Task:** S5-14

## Summary of Work

Added `ReplayGateway`, which loads versioned JSON fixtures, validates every
response through `m3.v1`, returns deterministic typed results, supports explicit
abstention, and fails closed for malformed or missing cases. It performs no
network access and requires no credential.

## Files Modified

- `apps/api/src/projecta_api/llm/replay.py`
- `apps/api/src/projecta_api/llm/__init__.py`
- `apps/api/tests/test_replay_gateway.py`
- `evaluation/sprint-5/replay_outputs.v1.json`

## Testing

- **Command:** `uv run pytest tests/test_replay_gateway.py tests/test_llm_gateway.py -q`
- **Coverage:** fixture loading, typed result, explicit abstention, and unknown-case fail-closed behavior.
