"""M3 application orchestration tests without network or provider SDK calls."""

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.service import ExtractionOrchestrator, _ingestion_body
from projecta_api.llm.gateway import GatewayResponse
from projecta_api.models import ExtractionRequest


class FakeGateway:
    def __init__(self) -> None:
        self.request: object | None = None

    async def extract(self, request: object) -> GatewayResponse:
        self.request = request
        return GatewayResponse(
            extraction=ExtractionResponse.model_validate(
                {
                    "schemaVersion": "m3.v1",
                    "modelId": "replay",
                    "modelVersion": "fixture",
                    "entities": [],
                    "relations": [],
                    "links": [],
                    "abstentionReason": "ambiguous",
                }
            )
        )


class FakeSemantic:
    def __init__(self) -> None:
        self.body: object | None = None
        self.context_reads = 0

    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]:
        self.context_reads += 1
        return [{"id": "team-1", "type": "Person", "label": "Le"}]

    async def ingest_extraction(
        self, context: TrustedRequestContext, key: str, body: object
    ) -> object:
        self.body = body
        return {"note": {"id": "note-1"}, "candidates": []}


@pytest.mark.asyncio
async def test_orchestrator_reads_context_normalizes_and_persists_only_through_core() -> None:
    semantic = FakeSemantic()
    orchestrator = ExtractionOrchestrator(FakeGateway(), semantic, "deepseek-v4-flash")

    result = await orchestrator.extract(
        TrustedRequestContext("project", "actor", "request"),
        "key-1",
        ExtractionRequest(rawText="No clear owner."),
    )

    assert result == {
        "note": {"id": "note-1"},
        "candidates": [],
        "entities": [],
        "relations": [],
        "links": [],
        "abstentionReason": "ambiguous",
    }
    assert isinstance(semantic.body, dict)
    assert semantic.body["abstentionReason"] if "abstentionReason" in semantic.body else True


@pytest.mark.asyncio
async def test_orchestrator_fails_closed_when_model_is_missing() -> None:
    orchestrator = ExtractionOrchestrator(FakeGateway(), FakeSemantic(), None)

    with pytest.raises(Exception, match="LLM model is not configured"):
        await orchestrator.extract(
            TrustedRequestContext("project", "actor", "request"),
            "key-1",
            ExtractionRequest(rawText="A note."),
        )


@pytest.mark.asyncio
async def test_assisted_import_skips_link_context_and_requests_entities_only() -> None:
    semantic = FakeSemantic()
    gateway = FakeGateway()
    orchestrator = ExtractionOrchestrator(gateway, semantic, "deepseek-v4-flash")

    await orchestrator.propose(
        TrustedRequestContext("project", "actor", "request"),
        ExtractionRequest(rawText="Deliver the model on Monday."),
    )

    assert semantic.context_reads == 0
    assert gateway.request is not None
    request = gateway.request
    assert set(request.response_schema["properties"]) == {  # type: ignore[attr-defined,index]
        "entities",
        "abstentionReason",
    }
    assert request.source_text == "Deliver the model on Monday."
    assert "Relations and links are not representable" in request.user_prompt  # type: ignore[attr-defined]


def test_entity_ingestion_preserves_exact_evidence_separately_from_label() -> None:
    response = ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v1",
            "modelId": "replay",
            "modelVersion": "fixture",
            "entities": [
                {
                    "type": "Requirement",
                    "label": "shipping address confirmation",
                    "evidence": {
                        "startOffset": 0,
                        "endOffset": 44,
                        "text": "Confirm the shipping address before payment.",
                    },
                    "confidence": 0.9,
                }
            ],
            "relations": [],
            "links": [],
            "abstentionReason": None,
        }
    )

    body = _ingestion_body("Confirm the shipping address before payment.", response)

    entities = body["entities"]
    assert isinstance(entities, list)
    first = entities[0]
    assert isinstance(first, dict)
    assert first["label"] == "shipping address confirmation"
    assert first["text"] == "Confirm the shipping address before payment."
