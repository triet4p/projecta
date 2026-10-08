"""S8 cross-boundary failure injection: one terminal error and no mutation."""

from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedRequestContext
from projecta_api.llm.gateway import GatewayRequest, GatewayResponse, NormalizedGatewayError
from projecta_api.main import create_app
from projecta_api.models import CaptureRequest, CaptureResponse
from projecta_api.semantic_core import HttpSemanticCoreClient


class MutationSpy:
    """Finite Semantic Core double that records every mutation boundary call."""

    def __init__(self) -> None:
        self.capture_calls = 0
        self.ingest_calls = 0

    async def readiness(self) -> bool:
        return True

    async def entity_link_context(self, context: TrustedRequestContext, limit: int = 50) -> list[dict[str, str]]:
        return []

    async def ingest_extraction(self, context: TrustedRequestContext, key: str, body: object) -> object:
        self.ingest_calls += 1
        return {"requestId": context.request_id, "status": "mutated"}

    async def capture(
        self, context: TrustedRequestContext, key: str, request: CaptureRequest
    ) -> CaptureResponse:
        self.capture_calls += 1
        return CaptureResponse.model_validate(
            {"requestId": context.request_id, "note": {"id": "note-01"}, "candidates": []}
        )

    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object:
        return {"requestId": context.request_id, "items": []}


class FailingGateway:
    def __init__(self, error_class: str) -> None:
        self.error_class = error_class
        self.calls = 0

    async def extract(self, request: GatewayRequest) -> GatewayResponse:
        self.calls += 1
        raise NormalizedGatewayError(self.error_class, "injected provider failure", retryable=True)  # type: ignore[arg-type]


class CrashingSemanticCore(MutationSpy):
    async def entity_link_context(self, context: TrustedRequestContext, limit: int = 50) -> list[dict[str, str]]:
        raise RuntimeError("injected API crash")


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        runtime_mode="headless",
        trusted_context_secret="test-secret",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://provider.example",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="test-model",
    )


def _headers(key: str) -> dict[str, str]:
    return {
        "X-Projecta-Project-Id": "ecommerce-checkout",
        "X-Projecta-Actor-Id": "le",
        "X-Projecta-Context-Secret": "test-secret",
        "X-Request-Id": "req-failure-matrix",
        "X-Operation-Id": "op-failure-matrix",
        "Idempotency-Key": key,
    }


def _extraction_body() -> dict[str, Any]:
    return {"rawText": "Confirm address."}


@pytest.mark.parametrize(
    ("error_class", "status", "code"),
    [
        ("timeout", 504, "PROVIDER_TIMEOUT"),
        ("rate_limit", 429, "PROVIDER_RATE_LIMITED"),
        ("schema_invalid", 502, "PROVIDER_RESPONSE_INVALID"),
    ],
)
async def test_provider_failures_are_one_terminal_error_without_mutation(
    error_class: str, status: int, code: str
) -> None:
    semantic = MutationSpy()
    gateway = FailingGateway(error_class)
    app = create_app(_settings(), semantic, gateway)  # type: ignore[arg-type]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/quick-notes/extractions",
            headers=_headers(f"provider-{error_class}"),
            json=_extraction_body(),
        )

    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["requestId"] == "req-failure-matrix"
    assert response.headers["X-Operation-Id"] == "op-failure-matrix"
    assert gateway.calls == 1
    assert semantic.ingest_calls == 0


async def test_api_crash_is_one_correlated_terminal_error_without_mutation() -> None:
    semantic = CrashingSemanticCore()
    app = create_app(_settings(), semantic)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/quick-notes/extractions",
            headers=_headers("api-crash"),
            json=_extraction_body(),
        )

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.json()["requestId"] == "req-failure-matrix"
    assert response.headers["X-Request-Id"] == "req-failure-matrix"
    assert semantic.ingest_calls == 0


@pytest.mark.parametrize(
    ("status", "payload", "expected_code"),
    [
        (422, {"code": "CANDIDATE_INVALID", "detail": "rejected"}, "CANDIDATE_INVALID"),
        (503, {"code": "INTERNAL_ERROR", "detail": "dependency unavailable"}, "SEMANTIC_CONTRACT_UNAVAILABLE"),
    ],
)
async def test_semantic_core_4xx_and_5xx_are_one_terminal_error(
    status: int, payload: dict[str, str], expected_code: str
) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json=payload)

    semantic = HttpSemanticCoreClient("http://semantic-core", httpx.MockTransport(handler))
    app = create_app(_settings(), semantic)
    body = {
        "rawText": "Confirm address.",
        "segments": [{"type": "requirement", "startOffset": 0, "endOffset": 16, "text": "Confirm address."}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", headers=_headers(f"semantic-{status}"), json=body)

    assert response.status_code == (422 if status == 422 else 503)
    assert response.json()["code"] == expected_code
    assert response.json()["requestId"] == "req-failure-matrix"
    assert calls == 1


async def test_semantic_core_invalid_success_response_is_terminal_without_mutation() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="not-json", headers={"content-type": "text/plain"})

    semantic = HttpSemanticCoreClient("http://semantic-core", httpx.MockTransport(handler))
    app = create_app(_settings(), semantic)
    body = {
        "rawText": "Confirm address.",
        "segments": [{"type": "requirement", "startOffset": 0, "endOffset": 16, "text": "Confirm address."}],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", headers=_headers("semantic-invalid"), json=body)

    assert response.status_code == 503
    assert response.json()["code"] == "SEMANTIC_CONTRACT_UNAVAILABLE"
    assert response.json()["requestId"] == "req-failure-matrix"
    assert calls == 1
