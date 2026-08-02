"""Smoke tests for the application composition root."""

from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.llm.gateway import GatewayResponse
from projecta_api.main import create_app
from projecta_api.models import ExtractionRequest


async def test_live_health_returns_live() -> None:
    """The scaffold exposes a dependency-free liveness endpoint."""
    settings = Settings(
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://api.deepseek.com",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="deepseek-v4-flash",
    )
    transport = ASGITransport(app=create_app(settings=settings))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


async def test_invalid_provider_evidence_is_not_reported_as_invalid_caller_input() -> None:
    """A valid caller request must not receive 400 for malformed model evidence."""

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
                                "confidence": 0.5,
                            }
                        ],
                        "relations": [],
                        "links": [],
                        "abstentionReason": None,
                    }
                )
            )

    class SemanticSpy:
        async def entity_link_context(
            self, context: TrustedRequestContext, limit: int = 50
        ) -> list[dict[str, str]]:
            return []

        async def ingest_extraction(
            self, context: TrustedRequestContext, key: str, body: object
        ) -> object:
            raise AssertionError("invalid provider output must not be persisted")

        async def capture(
            self, context: TrustedRequestContext, key: str, request: object
        ) -> object:
            raise AssertionError("not used")

        async def request(
            self,
            context: TrustedRequestContext,
            method: str,
            path: str,
            body: object | None = None,
            key: str | None = None,
        ) -> object:
            raise AssertionError("not used")

    settings = Settings(
        trusted_context_secret="test-secret",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://system-test.invalid",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="replay:invalid",
    )
    app = create_app(settings, SemanticSpy(), InvalidEvidenceGateway())  # type: ignore[arg-type]
    headers = {
        "X-Projecta-Project-Id": "project",
        "X-Projecta-Actor-Id": "actor",
        "X-Projecta-Context-Secret": "test-secret",
        "X-Request-Id": "req-invalid-provider",
        "Idempotency-Key": "extract-invalid-provider",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/v1/quick-notes/extractions",
            headers=headers,
            json=ExtractionRequest(rawText="source text").model_dump(mode="json", by_alias=True),
        )

    assert response.status_code == 503
    assert response.json()["code"] == "SEMANTIC_CONTRACT_UNAVAILABLE"
