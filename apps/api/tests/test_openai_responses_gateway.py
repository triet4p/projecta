"""Provider adapter tests using a mocked OpenAI-compatible client boundary."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from projecta_api.extraction.service import _response_schema
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


def _proposal_request() -> GatewayRequest:
    return GatewayRequest(
        schemaVersion="m3.v1",
        modelId="deepseek-v4-flash",
        systemPrompt="system",
        userPrompt="user",
        responseSchema={"type": "object", "properties": {}, "additionalProperties": False},
        sourceText="same phrase then same phrase",
    )


def _sampling_request() -> GatewayRequest:
    return GatewayRequest(
        schemaVersion="m3.v1",
        modelId="deepseek-v4-pro",
        systemPrompt="system",
        userPrompt="user",
        responseSchema={"type": "object", "properties": {}, "additionalProperties": False},
        temperature=0.0,
        topP=1.0,
    )


def test_adapter_fails_closed_without_credential() -> None:
    with pytest.raises(NormalizedGatewayError) as caught:
        OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="")

    assert caught.value.error_class == "configuration_invalid"


def test_adapter_disables_sdk_retries() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    assert gateway._client.max_retries == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_adapter_normalizes_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class FakeCompletions:
        async def create(self, **kwargs: object) -> object:
            assert "store" not in kwargs
            assert kwargs["response_format"] == {"type": "json_object"}
            assert kwargs["max_tokens"] == 4096
            assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
            assert "Exact JSON Schema to satisfy" in kwargs["messages"][0]["content"]  # type: ignore[index]
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content='{"entities": [], "relations": [], "links": [], "abstentionReason": "empty"}'
                        ),
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=3,
                    completion_tokens=4,
                    total_tokens=7,
                    completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
                ),
            )

    gateway._client.chat.completions = FakeCompletions()  # type: ignore[attr-defined]
    result = await gateway.extract(_request())

    assert result.extraction.abstention_reason == "empty"
    assert result.usage is not None
    assert result.usage.total_tokens == 7
    assert result.usage.reasoning_tokens == 0


@pytest.mark.asyncio
async def test_adapter_passes_explicit_sampling_configuration() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class FakeCompletions:
        async def create(self, **kwargs: object) -> object:
            assert kwargs["temperature"] == 0.0
            assert kwargs["top_p"] == 1.0
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content='{"entities": [], "relations": [], "links": [], "abstentionReason": "empty"}'
                        ),
                    )
                ],
                usage=None,
            )

    gateway._client.chat.completions = FakeCompletions()  # type: ignore[attr-defined]
    result = await gateway.extract(_sampling_request())

    assert result.extraction.abstention_reason == "empty"


@pytest.mark.asyncio
async def test_adapter_enforces_absolute_deadline() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class SlowCompletions:
        async def create(self, **kwargs: object) -> object:
            await asyncio.sleep(0.05)
            raise AssertionError("absolute deadline did not cancel the provider call")

    gateway._client.chat.completions = SlowCompletions()  # type: ignore[attr-defined]
    request = _request().model_copy(update={"timeout_seconds": 0.01})

    with pytest.raises(NormalizedGatewayError) as caught:
        await gateway.extract(request)

    assert caught.value.error_class == "timeout"
    assert caught.value.retryable is True


@pytest.mark.asyncio
async def test_adapter_fails_explicitly_when_output_hits_token_limit() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class TruncatedCompletions:
        async def create(self, **kwargs: object) -> object:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="length",
                        message=SimpleNamespace(content='{"entities": ['),
                    )
                ],
                usage=None,
            )

    gateway._client.chat.completions = TruncatedCompletions()  # type: ignore[attr-defined]

    with pytest.raises(NormalizedGatewayError) as caught:
        await gateway.extract(_request())

    assert caught.value.error_class == "empty_malformed"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_adapter_derives_assisted_import_offsets_from_explicit_occurrence() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class ProposalCompletions:
        async def create(self, **kwargs: object) -> object:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=(
                                '{"entities":[{"type":"Requirement","label":"same phrase",'
                                '"evidence":{"text":"same phrase","occurrence":2},'
                                '"confidence":0.9}],"abstentionReason":null}'
                            )
                        ),
                    )
                ],
                usage=None,
            )

    gateway._client.chat.completions = ProposalCompletions()  # type: ignore[attr-defined]
    result = await gateway.extract(_proposal_request())

    assert result.extraction.entities[0].evidence.start_offset == 17
    assert result.extraction.entities[0].evidence.end_offset == 28


@pytest.mark.asyncio
async def test_adapter_rejects_missing_assisted_import_occurrence() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class MissingOccurrenceCompletions:
        async def create(self, **kwargs: object) -> object:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=(
                                '{"entities":[{"type":"Requirement","label":"not present",'
                                '"evidence":{"text":"not present","occurrence":1},'
                                '"confidence":0.9}],"abstentionReason":null}'
                            )
                        ),
                    )
                ],
                usage=None,
            )

    gateway._client.chat.completions = MissingOccurrenceCompletions()  # type: ignore[attr-defined]

    with pytest.raises(NormalizedGatewayError) as caught:
        await gateway.extract(_proposal_request())

    assert caught.value.error_class == "invalid_evidence"
    assert caught.value.retryable is False


@pytest.mark.asyncio
async def test_adapter_materializes_m3_v2_evidence_for_entities_and_relations() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class V2Completions:
        async def create(self, **kwargs: object) -> object:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=(
                                '{"entities":['
                                '{"candidateId":"task-1","type":"Task","label":"Task",'
                                '"evidence":{"text":"Task","occurrence":1},"confidence":0.9},'
                                '{"candidateId":"requirement-1","type":"Requirement",'
                                '"label":"requirement","evidence":{"text":"requirement",'
                                '"occurrence":1},"confidence":0.9}],'
                                '"relations":[{"predicate":"implements","sourceEntityId":"task-1",'
                                '"targetEntityId":"requirement-1","evidence":{"text":"Task implements '
                                'requirement.","occurrence":1},"confidence":0.8}],'
                                '"links":[],"abstentionReason":null}'
                            )
                        ),
                    )
                ],
                usage=None,
            )

    gateway._client.chat.completions = V2Completions()  # type: ignore[attr-defined]
    request = _request().model_copy(
        update={
            "schema_version": "m3.v2",
            "source_text": "Task implements requirement.",
            "response_schema": _response_schema(schema_version="m3.v2"),
        }
    )
    result = await gateway.extract(request)

    assert result.extraction.schema_version == "m3.v2"
    assert result.extraction.entities[0].candidate_id == "task-1"
    assert result.extraction.relations[0].evidence.end_offset == 28


@pytest.mark.asyncio
async def test_adapter_exposes_structure_only_schema_diagnostic() -> None:
    gateway = OpenAIResponsesGateway(base_url="https://api.deepseek.com", api_key="test-key")

    class MalformedCompletions:
        async def create(self, **kwargs: object) -> object:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=(
                                '{"entities":[{"type":"Task","label":"secret task",'
                                '"evidence":{"text":"secret task","occurrence":1},'
                                '"confidence":0.9}],"relations":[],"links":[],'
                                '"abstentionReason":null}'
                            )
                        ),
                    )
                ],
                usage=None,
            )

    gateway._client.chat.completions = MalformedCompletions()  # type: ignore[attr-defined]
    request = _request().model_copy(
        update={
            "schema_version": "m3.v2",
            "response_schema": _response_schema(schema_version="m3.v2"),
        }
    )

    with pytest.raises(NormalizedGatewayError) as caught:
        await gateway.extract(request)

    assert caught.value.error_class == "schema_invalid"
    assert caught.value.diagnostic["errorType"] == "ValidationError"
    assert "secret task" not in json.dumps(caught.value.diagnostic)
    assert caught.value.diagnostic["payloadShape"]["kind"] == "object"
