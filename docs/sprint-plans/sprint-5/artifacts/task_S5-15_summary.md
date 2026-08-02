# Task Summary: S5-15 — Implement the approved provider adapter

**Sprint:** Sprint 5
**Task:** S5-15

## Summary of Work

Implemented the OpenAI-compatible Responses API adapter using `AsyncOpenAI`,
configured for the DeepSeek endpoint through `PROJECTA_LLM_BASE_URL` and
`PROJECTA_LLM_API_KEY`. It requests strict JSON Schema output, copies only
provider-neutral usage counters, injects the contract version/model metadata,
and maps timeout, rate-limit, connection, status, and malformed-output errors
to safe gateway errors. SDK types do not cross the adapter boundary.

## Files Modified

- `apps/api/pyproject.toml`
- `apps/api/src/projecta_api/llm/openai_responses.py`
- `apps/api/src/projecta_api/llm/__init__.py`
- `apps/api/tests/test_openai_responses_gateway.py`

## Testing

- **Command:** `uv run pytest tests/test_openai_responses_gateway.py -q`
- **Coverage:** missing credential, strict JSON Schema request, structured output normalization, and usage mapping.
