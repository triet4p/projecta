"""Cross-cutting M3 contract regressions, including no persistence on failure."""

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.service import ExtractionOrchestrator
from projecta_api.llm.gateway import GatewayResponse, NormalizedGatewayError
from projecta_api.models import ExtractionRequest


class InvalidEvidenceGateway:
    async def extract(self, request: object) -> GatewayResponse:
        return GatewayResponse(
            extraction=ExtractionResponse.model_validate(
                {
                    "schemaVersion": "m3.v1",
                    "modelId": "replay",
                    "modelVersion": "fixture",
                    "entities": [
                        {
                            "type": "Requirement",
                            "label": "wrong",
                            "evidence": {"startOffset": 0, "endOffset": 5, "text": "wrong"},
                            "confidence": "0.5",
                        }
                    ],
                    "relations": [],
                    "links": [],
                }
            )
        )


class PersistenceSpy:
    async def entity_link_context(self, context: TrustedRequestContext, limit: int = 50) -> list[dict[str, str]]:
        return []

    async def ingest_extraction(self, context: TrustedRequestContext, key: str, body: object) -> object:
        raise AssertionError("persistence must not be called after normalization failure")


@pytest.mark.asyncio
async def test_invalid_evidence_stops_before_persistence() -> None:
    service = ExtractionOrchestrator(InvalidEvidenceGateway(), PersistenceSpy(), "deepseek-v4-flash")

    with pytest.raises(NormalizedGatewayError) as caught:
        await service.extract(
            TrustedRequestContext("project", "actor", "request"),
            "key",
            ExtractionRequest(rawText="source text"),
        )

    assert caught.value.error_class == "invalid_evidence"
