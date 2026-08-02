# Task Summary: S5-16 — Implement model configuration and resilience

**Sprint:** Sprint 5
**Task:** S5-16

## Summary of Work

Added configurable DeepSeek/OpenAI-compatible endpoint, secret, model,
timeout, and retry settings. Added `ResilientGateway` with at most three total
attempts, exponential backoff cap, and retry only for normalized retryable
errors. Non-retryable schema/configuration failures fail immediately; secrets
are represented as `SecretStr` and are not exposed by settings repr.

## Files Modified

- `apps/api/src/projecta_api/config.py`
- `apps/api/src/projecta_api/llm/resilience.py`
- `apps/api/src/projecta_api/llm/__init__.py`
- `apps/api/tests/test_llm_resilience.py`
- `apps/api/tests/test_llm_config.py`

## Testing

- **Command:** `uv run pytest tests/test_llm_resilience.py tests/test_llm_config.py -q`
- **Coverage:** bounded retry/backoff, no retry on schema failure, endpoint/model configuration, and secret redaction.
