"""OpenAI-compatible Responses API adapter, including DeepSeek routing."""

import asyncio
import json
from typing import Any, cast

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
)

from projecta_api.extraction.contracts import ExtractionResponse, UsageMetadata
from projecta_api.llm.gateway import GatewayRequest, GatewayResponse, NormalizedGatewayError


class OpenAIResponsesGateway:
    """Translate the OpenAI-compatible Responses API into Projecta types."""

    def __init__(self, *, base_url: str, api_key: str) -> None:
        if not api_key:
            raise NormalizedGatewayError(
                "configuration_invalid",
                "live provider credential is not configured",
                retryable=False,
            )
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=httpx.Timeout(60.0, connect=10.0, read=60.0, write=30.0, pool=10.0),
        )

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        """Call strict structured output and normalize response/error details."""
        try:
            async with asyncio.timeout(request.timeout_seconds):
                if request.model_id.startswith("deepseek-"):
                    response, output_text = await self._extract_deepseek_chat(request)
                else:
                    response, output_text = await self._extract_responses(request)
        except (APITimeoutError, TimeoutError) as error:
            raise NormalizedGatewayError(
                "timeout", "provider request timed out", retryable=True
            ) from error
        except RateLimitError as error:
            raise NormalizedGatewayError(
                "rate_limit", "provider request was rate limited", retryable=True
            ) from error
        except APIConnectionError as error:
            raise NormalizedGatewayError(
                "provider_failure", "provider connection failed", retryable=True
            ) from error
        except APIStatusError as error:
            retryable = error.status_code in {408, 409, 429} or error.status_code >= 500
            if error.status_code == 429:
                error_class = "rate_limit"
            elif error.status_code in {400, 403}:
                error_class = "refusal"
            else:
                error_class = "provider_failure"
            raise NormalizedGatewayError(
                error_class, "provider returned an unsuccessful response", retryable=retryable
            ) from error
        except OpenAIError as error:
            raise NormalizedGatewayError(
                "provider_failure", "provider request failed", retryable=False
            ) from error

        if not isinstance(output_text, str) or not output_text:
            raise NormalizedGatewayError(
                "empty_malformed", "provider returned no structured output", retryable=False
            )
        payload: Any = None
        try:
            payload = json.loads(output_text)
            if request.source_text is not None:
                payload = _materialize_entity_evidence(payload, request.source_text)
            usage = _usage(getattr(response, "usage", None))
            extraction = ExtractionResponse.model_validate(
                {
                    **payload,
                    "schemaVersion": request.schema_version,
                    "modelId": request.model_id,
                    "modelVersion": request.model_id,
                    "usage": usage.model_dump(by_alias=True) if usage else None,
                }
            )
        except (TypeError, ValueError) as error:
            raise NormalizedGatewayError(
                "schema_invalid",
                "provider output did not match m3.v1",
                retryable=False,
                diagnostic=_schema_diagnostic(payload, output_text, error),
            ) from error
        return GatewayResponse(extraction=extraction, usage=usage)

    async def _extract_deepseek_chat(self, request: GatewayRequest) -> tuple[Any, str | None]:
        """Use DeepSeek's documented V4 interface with thinking explicitly disabled."""
        schema_json = json.dumps(
            request.response_schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        response: Any = await self._client.chat.completions.create(
            model=request.model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{request.system_prompt}\nExact JSON Schema to satisfy:\n{schema_json}"
                    ),
                },
                {"role": "user", "content": request.user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=request.max_output_tokens,
            extra_body={"thinking": {"type": "disabled"}},
            timeout=request.timeout_seconds,
        )
        choices = getattr(response, "choices", None)
        if not choices:
            return response, None
        choice = choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise NormalizedGatewayError(
                "empty_malformed",
                "provider output exceeded the configured token limit",
                retryable=False,
            )
        message = getattr(choice, "message", None)
        return response, getattr(message, "content", None)

    async def _extract_responses(self, request: GatewayRequest) -> tuple[Any, str | None]:
        """Use strict Responses JSON Schema output for compatible providers."""
        response: Any = await self._client.responses.create(
            model=request.model_id,
            instructions=request.system_prompt,
            input=request.user_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "projecta_extraction",
                    "schema": dict(request.response_schema),
                    "strict": True,
                }
            },
            max_output_tokens=request.max_output_tokens,
            timeout=request.timeout_seconds,
        )
        return response, getattr(response, "output_text", None)


def _usage(value: Any) -> UsageMetadata | None:
    """Copy only numeric usage counters from an SDK response object."""
    if value is None:
        return None
    output_details = getattr(value, "output_tokens_details", None)
    if output_details is None:
        output_details = getattr(value, "completion_tokens_details", None)
    return UsageMetadata(
        inputTokens=getattr(value, "input_tokens", None) or getattr(value, "prompt_tokens", None),
        outputTokens=getattr(value, "output_tokens", None)
        or getattr(value, "completion_tokens", None),
        totalTokens=getattr(value, "total_tokens", None),
        reasoningTokens=getattr(output_details, "reasoning_tokens", None),
    )


def _materialize_entity_evidence(payload: Any, source_text: str) -> Any:
    """Derive exact offsets for every candidate category from quote occurrences."""
    if not isinstance(payload, dict):
        return payload
    typed_payload = cast(dict[str, Any], payload)
    for category in ("entities", "relations", "links"):
        candidates = typed_payload.get(category)
        if not isinstance(candidates, list):
            continue
        for candidate_index, raw_candidate in enumerate(cast(list[Any], candidates)):
            if not isinstance(raw_candidate, dict):
                continue
            candidate = cast(dict[str, Any], raw_candidate)
            raw_evidence = candidate.get("evidence")
            if not isinstance(raw_evidence, dict):
                continue
            evidence = cast(dict[str, Any], raw_evidence)
            text = evidence.get("text")
            occurrence = evidence.get("occurrence")
            if not isinstance(text, str) or not text or not isinstance(occurrence, int):
                continue
            starts: list[int] = []
            cursor = 0
            while True:
                start = source_text.find(text, cursor)
                if start < 0:
                    break
                starts.append(start)
                cursor = start + 1
            if occurrence < 1 or occurrence > len(starts):
                raise NormalizedGatewayError(
                    "invalid_evidence",
                    "provider evidence occurrence does not exist in source text",
                    retryable=False,
                    diagnostic={
                        "category": category,
                        "candidateIndex": candidate_index,
                        "payloadShape": _payload_shape(payload),
                    },
                )
            start = starts[occurrence - 1]
            evidence.clear()
            evidence.update({"startOffset": start, "endOffset": start + len(text), "text": text})
    return typed_payload


def _payload_shape(value: Any, *, depth: int = 0) -> object:
    """Return structure-only diagnostics; never persist provider string values."""
    if depth > 4:
        return {"kind": "truncated"}
    if isinstance(value, dict):
        return {
            "kind": "object",
            "keys": sorted(str(key) for key in value),
            "fields": {
                str(key): _payload_shape(item, depth=depth + 1)
                for key, item in value.items()
            },
        }
    if isinstance(value, list):
        return {
            "kind": "array",
            "length": len(value),
            "items": [_payload_shape(item, depth=depth + 1) for item in value[:5]],
        }
    if isinstance(value, str):
        return {"kind": "string", "length": len(value)}
    if value is None:
        return {"kind": "null"}
    return {"kind": type(value).__name__}


def _schema_diagnostic(payload: Any, output_text: str, error: Exception) -> dict[str, object]:
    errors_method = getattr(error, "errors", None)
    validation_errors: list[dict[str, object]] = []
    if callable(errors_method):
        for item in errors_method()[:20]:
            if isinstance(item, dict):
                validation_errors.append(
                    {
                        "location": [str(part) for part in item.get("loc", ())],
                        "type": str(item.get("type", "unknown")),
                    }
                )
    return {
        "outputTextLength": len(output_text),
        "payloadShape": _payload_shape(payload),
        "validationErrors": validation_errors,
        "errorType": type(error).__name__,
    }
