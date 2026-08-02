# M3 Provider Decision

**Task:** S5-08
**Status:** IMPLEMENTATION_AUTHORIZED; provider gate bypassed under the user instruction.

## Selected Adapter

The first live adapter uses the OpenAI-compatible Responses API shape through
DeepSeek's endpoint, documented at
`https://api-docs.deepseek.com/guides/responses_api`. It uses a strict JSON
Schema generated from the versioned Pydantic extraction contract. The provider
response is translated immediately into Projecta gateway types; OpenAI SDK
classes, response objects, and error types do not cross the adapter boundary.

## Configuration and Credential Boundary

- `PROJECTA_LLM_TYPE` must be `openai-response` or `openai`.
- `PROJECTA_LLM_BASE_URL`, `PROJECTA_LLM_API_KEY`, and `PROJECTA_LLM_MODEL` are
  required deployment configuration; none has a source-code default or fallback.
- `PROJECTA_LLM_API_KEY` is injected by the deployment secret boundary only.
  It must never be accepted in request JSON, committed files, logs, telemetry,
  or exception details.
- Timeout and bounded retry policy are fixed operational safety limits; provider
  identity, endpoint, credential, and model always come from the four required
  `PROJECTA_LLM_*` variables. Raw provider payloads are not persisted.
- Canonical CI uses the replay adapter. Live provider evaluation is opt-in and
  requires an explicitly supplied credential.

## Replacement Conditions

Replace or add an adapter when measured quality, cost, latency, data handling,
availability, or deployment policy requires it. A replacement must implement
the same `LLMGateway` contract and pass the same schema, error, evidence,
normalization, and evaluation suites without changing ontology or API shapes.

This decision does not release the v0.4 ontology draft and does not authorize
production or sensitive data submission.
