# Task Summary: Shared operation-correlation model

**Sprint:** Sprint 8
**Task:** S8-12

## Summary of Work

Added a bounded correlation model with server-owned `requestId` and
`operationId` identities. The API boundary now normalizes missing or unsafe
correlation hints, preserves the existing server-owned experience context,
adds both IDs to response headers, forwards them to Semantic Core, and the Web
client/Nginx path carries both headers. Semantic Core accepts the operation
identity while preserving two-argument test/runtime construction compatibility.

## Files Modified

* [correlation.py](../../../../apps/api/src/projecta_api/correlation.py) - Correlation ID validation, generation, and header model.
* [context.py](../../../../apps/api/src/projecta_api/context.py) - API middleware and trusted context propagation.
* [main.py](../../../../apps/api/src/projecta_api/main.py) - Public problem response correlation headers.
* [semantic_core.py](../../../../apps/api/src/projecta_api/semantic_core.py) - Downstream correlation forwarding.
* [client.ts](../../../../apps/web/src/api/client.ts) - Browser operation header.
* [nginx.conf](../../../../apps/web/nginx.conf) - Proxy operation header and single-attempt timeout alignment.
* [TrustedProjectContext.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/TrustedProjectContext.java) - Semantic Core operation context.
* [SemanticCoreApplication.java](../../../../services/semantic-core/src/main/java/org/projecta/semanticcore/SemanticCoreApplication.java) - Core problem/header correlation.
* [test_correlation.py](../../../../apps/api/tests/test_correlation.py) - Correlation generation/reuse tests.
* [test_main.py](../../../../apps/api/tests/test_main.py), [test_capture_contract.py](../../../../apps/api/tests/test_capture_contract.py), [client.test.ts](../../../../apps/web/src/api/client.test.ts) - Response and propagation regressions.

## Testing

* **Test File:** API correlation, main, capture, interactive configuration, M2/M3 compatibility; Web API client; Semantic Core Maven suite.
* **Status:** Passed.
* **Execution Command:** `uv run pytest -q tests/test_correlation.py tests/test_main.py tests/test_capture_contract.py`; `uv run pytest -q tests/test_interactive_configuration.py tests/test_m3_e2e.py tests/test_m2_e2e.py`; `npm test -- --run src/api/client.test.ts`; `mvn --batch-mode "-Dspotless.check.skip=true" test`.

## Additional Notes

Existing three-argument `TrustedRequestContext` and two-argument
`TrustedProjectContext` construction remain compatible. Correlation IDs are
diagnostic identities only and are not authorization credentials.
