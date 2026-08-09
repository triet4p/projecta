# Task Summary: Provider error identity at the API boundary

**Sprint:** Sprint 8
**Task:** S8-15

## Summary of Work

Expanded normalized provider error classes for empty/malformed output,
refusal, and policy rejection. Provider HTTP status handling now preserves
safe identity, and the Application API maps normalized classes to the approved
finite public taxonomy with sanitized status/title/detail. Provider payloads,
raw detail, and unsafe evidence text are not returned.

## Files Modified

* [gateway.py](../../../../apps/api/src/projecta_api/llm/gateway.py) - Closed normalized provider error class set.
* [openai_responses.py](../../../../apps/api/src/projecta_api/llm/openai_responses.py) - Status/refusal/empty-output classification.
* [main.py](../../../../apps/api/src/projecta_api/main.py) - Finite sanitized public mapping.
* [test_error_mapping.py](../../../../apps/api/tests/test_error_mapping.py) - Public mapping matrix.
* [test_main.py](../../../../apps/api/tests/test_main.py) - Invalid evidence public behavior regression.

## Testing

* **Test File:** [test_error_mapping.py](../../../../apps/api/tests/test_error_mapping.py), [test_main.py](../../../../apps/api/tests/test_main.py), provider gateway tests.
* **Status:** Passed.
* **Execution Command:** `uv run pytest -q tests/test_error_mapping.py tests/test_main.py tests/test_openai_responses_gateway.py tests/test_llm_gateway.py`; `uv run ruff check src/projecta_api/correlation.py src/projecta_api/startup.py src/projecta_api/context.py src/projecta_api/main.py src/projecta_api/llm`

## Additional Notes

The released `SEMANTIC_CONTRACT_UNAVAILABLE` alias is not used as a new
provider catch-all. API snapshot regeneration remains a later contract task.
