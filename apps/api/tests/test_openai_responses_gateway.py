"""Provider adapter tests using a mocked OpenAI-compatible client boundary."""

from types import SimpleNamespace

import pytest

from projecta_api.llm.gateway import GatewayRequest, NormalizedGatewayError
from projecta_api.llm.openai_responses import OpenAIResponsesGateway


def _request() -> GatewayRequest:
    return GatewayRequest(
        schemaVersion="m3.v1",
        modelId="deepseek-v4-flash",
        systemPrompt="system",
        userPrompt="user",
        responseSchema={"type": "object", "properties": {}, "additionalProperties": False},
    )


def test_adapter_fails_closed_without_credential() -> None:
    with pytest.raises(NormalizedGatewayError) as caught:
        OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="")

    assert caught.value.error_class == "configuration_invalid"


@pytest.mark.asyncio
async def test_adapter_normalizes_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class FakeResponses:
        async def create(self, **kwargs: object) -> object:
            assert "store" not in kwargs
            assert kwargs["text"]["format"]["type"] == "json_schema"  # type: ignore[index]
            return SimpleNamespace(
                output_text='{"entities": [], "relations": [], "links": [], "abstentionReason": "empty"}',
                usage=SimpleNamespace(input_tokens=3, output_tokens=4, total_tokens=7),
            )

    gateway._client.responses = FakeResponses()  # type: ignore[attr-defined]
    result = await gateway.extract(_request())

    assert result.extraction.abstention_reason == "empty"
    assert result.usage is not None
    assert result.usage.total_tokens == 7
