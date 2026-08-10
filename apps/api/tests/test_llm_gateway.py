"""Tests for the provider-neutral gateway boundary."""

import pytest
from pydantic import ValidationError

from projecta_api.llm.gateway import GatewayRequest, NormalizedGatewayError


def test_gateway_request_rejects_provider_specific_or_arbitrary_fields() -> None:
    with pytest.raises(ValidationError):
        GatewayRequest.model_validate(
            {
                "schemaVersion": "m3.v1",
                "modelId": "replay",
                "systemPrompt": "system",
                "userPrompt": "user",
                "responseSchema": {"type": "object"},
                "openaiResponseFormat": {"type": "json_schema"},
            }
        )


def test_gateway_request_has_bounded_timeout() -> None:
    with pytest.raises(ValidationError):
        GatewayRequest.model_validate(
            {
                "schemaVersion": "m3.v1",
                "modelId": "replay",
                "systemPrompt": "system",
                "userPrompt": "user",
                "responseSchema": {"type": "object"},
                "timeoutSeconds": 121,
            }
        )


def test_gateway_request_has_bounded_output_budget() -> None:
    with pytest.raises(ValidationError):
        GatewayRequest.model_validate(
            {
                "schemaVersion": "m3.v1",
                "modelId": "replay",
                "systemPrompt": "system",
                "userPrompt": "user",
                "responseSchema": {"type": "object"},
                "maxOutputTokens": 16_385,
            }
        )


def test_normalized_gateway_error_exposes_only_safe_fields() -> None:
    error = NormalizedGatewayError("rate_limit", "provider request rate limited", retryable=True)

    assert error.error_class == "rate_limit"
    assert error.retryable is True
    assert "provider request" in error.detail
