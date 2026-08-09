# Task Summary: Explicit API route dependencies

**Sprint:** Sprint 8
**Task:** S8-16

## Summary of Work

Replaced missing route dependency `ValueError`/`RuntimeError` paths with one
finite sanitized `CONFIGURATION_INVALID` `503` response. Retrieval,
extraction, runtime configuration, provider checker, and configuration service
are now required at their route boundary. Unexpected configuration resolution
errors are normalized. Readiness no longer reports synthetic `ready/injected`
for an injected client without a real readiness probe, and direct problem
construction generates safe correlation IDs instead of returning `unknown`.

## Files Modified

* [routes.py](../../../../apps/api/src/projecta_api/routes.py) - Required dependency guard and finite configuration failures.
* [main.py](../../../../apps/api/src/projecta_api/main.py) - No synthetic readiness and safe problem correlation.
* [test_main.py](../../../../apps/api/tests/test_main.py) - Readiness regression for unprobed injected clients.

## Testing

* **Test File:** API main, capture, interactive configuration, and retrieval tests.
* **Status:** Passed.
* **Execution Command:** `uv run ruff check src/projecta_api/routes.py src/projecta_api/main.py`; `uv run pytest -q tests/test_main.py tests/test_capture_contract.py tests/test_interactive_configuration.py tests/test_m4_retrieval.py`

## Additional Notes

Domain-valid empty results remain allowed; this task only removes missing
dependency and synthetic-health substitutions.
