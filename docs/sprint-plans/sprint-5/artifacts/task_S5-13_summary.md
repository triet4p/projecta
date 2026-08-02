# Task Summary: S5-13 — Implement the provider-neutral LLM gateway

**Sprint:** Sprint 5
**Task:** S5-13

## Summary of Work

Added the typed `LLMGateway` protocol, bounded `GatewayRequest`, typed
`GatewayResponse`, and normalized retry-aware error interface. The boundary
rejects extra provider fields and does not expose SDK types, raw payloads,
credentials, RDF, graph names, or SPARQL.

## Files Modified

- `apps/api/src/projecta_api/llm/gateway.py`
- `apps/api/src/projecta_api/llm/__init__.py`
- `apps/api/tests/test_llm_gateway.py`

## Testing

- **Command:** `uv run pytest tests/test_llm_gateway.py tests/test_extraction_contracts.py tests/test_extraction_prompt.py -q`
- **Coverage:** strict request boundary, timeout cap, and safe normalized error behavior.
