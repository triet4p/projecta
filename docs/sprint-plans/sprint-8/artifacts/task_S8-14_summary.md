# Task Summary: Explicit provider retry modes

**Sprint:** Sprint 8
**Task:** S8-14

## Summary of Work

Made `ResilientGateway` mode-aware and changed all Application API interactive
gateway construction to `interactive-single-attempt` with zero automatic
retries. Explicit recovery/health modes retain bounded retry behavior, while
the evaluation mode permits only its declared bounded `invalid_evidence`
exception. Generic schema-invalid output is no longer retryable.

## Files Modified

* [resilience.py](../../../../apps/api/src/projecta_api/llm/resilience.py) - Explicit retry modes, attempt budgets, and eligible error classes.
* [main.py](../../../../apps/api/src/projecta_api/main.py) - Interactive gateway composition with one attempt.
* [openai_responses.py](../../../../apps/api/src/projecta_api/llm/openai_responses.py) - Schema-invalid output is terminal.
* [test_llm_resilience.py](../../../../apps/api/tests/test_llm_resilience.py) - Explicit-mode and interactive single-attempt regressions.

## Testing

* **Test File:** [test_llm_resilience.py](../../../../apps/api/tests/test_llm_resilience.py), [test_llm_gateway.py](../../../../apps/api/tests/test_llm_gateway.py), [test_openai_responses_gateway.py](../../../../apps/api/tests/test_openai_responses_gateway.py), [test_main.py](../../../../apps/api/tests/test_main.py)
* **Status:** Passed.
* **Execution Command:** `uv run pytest -q tests/test_llm_resilience.py tests/test_llm_gateway.py tests/test_openai_responses_gateway.py tests/test_main.py`

## Additional Notes

The generic helper still supports bounded operator/health/evaluation modes, but
the product composition cannot inherit that behavior accidentally.
