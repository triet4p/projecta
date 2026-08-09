# Task Summary: Provider-attempt structured events

**Sprint:** Sprint 8
**Task:** S8-17

## Summary of Work

Added a strict `s8.logging.v1` provider-attempt event model and wired it into
the mode-aware gateway. Each attempt emits start/completed events carrying the
same request/operation IDs, one-based attempt, timeout, model/profile revision,
latency, safe error class, retryability, terminal outcome, and optional numeric
usage counters. Prompts, source text, request bodies, and provider payloads are
not accepted by the event model.

## Files Modified

* [telemetry.py](../../../../apps/api/src/projecta_api/llm/telemetry.py) - Strict provider-attempt event model/emitter.
* [gateway.py](../../../../apps/api/src/projecta_api/llm/gateway.py) - Correlation/profile fields on internal gateway request.
* [resilience.py](../../../../apps/api/src/projecta_api/llm/resilience.py) - Attempt start/terminal event wiring.
* [service.py](../../../../apps/api/src/projecta_api/extraction/service.py) - Request/operation/profile propagation.
* [main.py](../../../../apps/api/src/projecta_api/main.py) - Provider identity at gateway composition.
* [test_llm_resilience.py](../../../../apps/api/tests/test_llm_resilience.py) - Event pairing/correlation/redaction regression.

## Testing

* **Test File:** [test_llm_resilience.py](../../../../apps/api/tests/test_llm_resilience.py), extraction orchestration, and main API tests.
* **Status:** Passed.
* **Execution Command:** `uv run pytest -q tests/test_llm_resilience.py tests/test_extraction_orchestration.py tests/test_main.py`; `uv run ruff check src/projecta_api/llm src/projecta_api/extraction/service.py src/projecta_api/main.py tests/test_llm_resilience.py`

## Additional Notes

The event model is application-level structured logging metadata; it does not
persist prompts, provider payloads, or semantic graph data.
