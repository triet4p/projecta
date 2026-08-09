"""OpenAI-compatible Responses API adapter, including DeepSeek routing."""

import json
from typing import Any

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
                "configuration_invalid", "live provider credential is not configured", retryable=False
            )
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        """Call strict structured output and normalize response/error details."""
        try:
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
                timeout=request.timeout_seconds,
            )
        except APITimeoutError as error:
            raise NormalizedGatewayError("timeout", "provider request timed out", retryable=True) from error
        except RateLimitError as error:
            raise NormalizedGatewayError("rate_limit", "provider request was rate limited", retryable=True) from error
        except APIConnectionError as error:
            raise NormalizedGatewayError("provider_failure", "provider connection failed", retryable=True) from error
        except APIStatusError as error:
            retryable = error.status_code in {408, 409, 429} or error.status_code >= 500
            if error.status_code == 429:
                error_class = "rate_limit"
            elif error.status_code in {400, 403}:
                error_class = "refusal"
            else:
                error_class = "provider_failure"
            raise NormalizedGatewayError(error_class, "provider returned an unsuccessful response", retryable=retryable) from error
        except OpenAIError as error:
            raise NormalizedGatewayError("provider_failure", "provider request failed", retryable=False) from error

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text:
            raise NormalizedGatewayError("empty_malformed", "provider returned no structured output", retryable=False)
        try:
            payload = json.loads(output_text)
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
            raise NormalizedGatewayError("schema_invalid", "provider output did not match m3.v1", retryable=False) from error
        return GatewayResponse(extraction=extraction, usage=usage)


def _usage(value: Any) -> UsageMetadata | None:
    """Copy only numeric usage counters from an SDK response object."""
    if value is None:
        return None
    return UsageMetadata(
        inputTokens=getattr(value, "input_tokens", None),
        outputTokens=getattr(value, "output_tokens", None),
        totalTokens=getattr(value, "total_tokens", None),
    )
