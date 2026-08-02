# M3 Model-Provider Adapter Benchmark

**Status:** IMPLEMENTATION_BASELINE
**Task:** S5-07
**Benchmark date:** 2026-08-02

## Scope and Method

Compared provider capabilities relevant to M3 extraction: strict structured
output, schema/Pydantic ergonomics, usage metadata, timeout/error handling,
data handling, cost/latency control, local/CI testability, and SDK isolation.
The benchmark evaluates adapters, not model quality; replay fixtures remain the
canonical deterministic test path.

## Comparison

| Option | Structured output | Usage/error surface | Data and operations | Local/CI | Adapter assessment |
|---|---|---|---|---|---|
| OpenAI Responses API | Native JSON Schema structured outputs with strict mode; Python SDK/Pydantic helpers | Typed response status/refusal and usage metadata are available; client timeout/retry can be bounded | Requires explicit storage/data-control configuration and credential boundary | Replay-friendly through gateway; provider tests opt-in | Strong first adapter fit; mature typed contract and simple extraction call |
| Google Gemini API | JSON Schema/Pydantic structured output, but documented as a supported subset; semantic validation remains application responsibility | Response metadata and provider errors require adapter normalization | Google API key/service boundary; schema complexity and model/tool combinations need explicit limits | Replay-friendly through gateway; provider tests opt-in | Strong alternative; schema-subset behavior requires more contract probing |
| Anthropic Messages API | JSON-shaped tool input via `input_schema`; extraction can use a tool contract, but it is not the same native final-response JSON Schema surface | `tool_use`/stop reasons and token usage need normalization | API key and tool-use payload controls; tool schemas add input tokens | Replay-friendly; SDK isolation straightforward | Viable adapter, but tool-use envelope adds mapping and refusal cases |
| vLLM OpenAI-compatible server | JSON Schema/structured-output backends; support depends on model/backend and server configuration | OpenAI-compatible response/usage surface; deployment owns timeout and observability | Data stays under Projecta deployment control; GPU/model operations become the burden | Best privacy/local test option when hardware/model is available | Strong later adapter, not the first sprint provider because runtime/model ops are extra scope |

## Decision Criteria and Result

For this vertical slice, structured-output reliability and typed Python
integration outweigh raw model breadth. The gateway must expose only
provider-neutral request/response/error types; the chosen adapter cannot leak
SDK classes into domain or Semantic Core code. All options remain replaceable
behind the same interface, and no live provider is required for canonical CI.

OpenAI and Gemini are the two strongest hosted candidates for the first
adapter. Anthropic remains a supported future adapter through tool-schema
mapping. vLLM is the privacy/local option once model packaging and hardware
are justified. S5-08 records the selected first provider and exact credential
boundary before adding any SDK dependency.

## Evidence

- [OpenAI structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) documents JSON Schema structured outputs, strict adherence, refusals, and Pydantic helpers.
- [OpenAI Responses API reference](https://platform.openai.com/docs/api-reference/responses-streaming) documents structured response formats and response status/usage surfaces.
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output) documents JSON Schema/Pydantic support, the supported schema subset, and the need for application semantic validation.
- [Anthropic tool use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) documents JSON Schema `input_schema` tool contracts and `tool_use` response handling.
- [vLLM structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/) documents JSON Schema guided decoding and backend/model-dependent support.

## Risks

Provider claims can change with model/API versions. The adapter must pin and
record model configuration, prompt/schema versions, and usage metadata; live
evaluation is opt-in. No provider-specific behavior becomes a domain contract.
