"""Contract tests for trusted typed Quick Note capture."""

from datetime import UTC, datetime

import httpx
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedRequestContext
from projecta_api.main import create_app
from projecta_api.models import CaptureRequest, CaptureResponse
from projecta_api.semantic_core import HttpSemanticCoreClient, SemanticCoreProblem


class FakeSemanticCoreClient:
    """In-memory finite client used to prove FastAPI never needs Fuseki."""

    async def capture(
        self, context: TrustedRequestContext, key: str, request: CaptureRequest
    ) -> CaptureResponse:
        return CaptureResponse.model_validate(
            {
                "requestId": context.request_id,
                "note": {"id": "note-01", "recordedAt": datetime(2026, 7, 31, tzinfo=UTC)},
                "candidates": [
                    {"id": "cand-01", "sourceItemId": "item-01", "status": "extracted"}
                ],
            }
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

    async def entity_link_context(
        self, context: TrustedRequestContext, limit: int = 50
    ) -> list[dict[str, str]]:
        return [{"id": "Requirement--req-01", "type": "Requirement", "label": "Checkout"}]


def app_headers() -> dict[str, str]:
    """Return headers that a trusted deployment adapter would inject."""
    return {
        "X-Projecta-Project-Id": "ecommerce-checkout",
        "X-Projecta-Actor-Id": "le",
        "X-Projecta-Context-Secret": "test-secret",
        "X-Request-Id": "req-01",
    }


def _make_settings(secret: str) -> Settings:
    return Settings(
        trusted_context_secret=secret,
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://api.deepseek.com",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="deepseek-v4-flash",
    )


async def test_link_context_read_is_project_scoped_and_bounded() -> None:
    app = create_app(_make_settings("test-secret"), FakeSemanticCoreClient())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/v1/entities/link-context?limit=10",
            headers=app_headers(),
        )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "req-01"
    assert response.headers["X-Operation-Id"]
    assert response.json() == {
        "requestId": "req-01",
        "entities": [
            {"id": "Requirement--req-01", "type": "Requirement", "label": "Checkout"}
        ],
    }


async def test_capture_requires_trusted_context() -> None:
    """Anonymous public calls cannot choose a project or actor."""
    app = create_app(_make_settings("test-secret"), FakeSemanticCoreClient())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", json={"rawText": "A", "segments": []})
    assert response.status_code == 401


async def test_capture_rejects_context_when_deployment_secret_is_missing() -> None:
    """Missing deployment configuration cannot become an unauthenticated scope selector."""
    app = create_app(_make_settings(""), FakeSemanticCoreClient())
    headers = app_headers() | {"Idempotency-Key": "capture-missing-secret"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/quick-notes",
            headers=headers,
            json={"rawText": "A", "segments": [{"type": "task", "startOffset": 0, "endOffset": 1, "text": "A"}]},
        )
    assert response.status_code == 401


async def test_capture_validates_exact_offsets_and_returns_opaque_ids() -> None:
    """A valid typed note is forwarded only after canonical local validation."""
    app = create_app(_make_settings("test-secret"), FakeSemanticCoreClient())
    headers = app_headers() | {"Idempotency-Key": "capture-01"}
    body = {
        "rawText": "Add address confirmation.",
        "segments": [
            {
                "type": "requirement",
                "startOffset": 0,
                "endOffset": 25,
                "text": "Add address confirmation.",
            }
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", headers=headers, json=body)
    assert response.status_code == 201
    assert response.json()["candidates"][0]["id"] == "cand-01"


async def test_legacy_confirmation_forwards_only_the_semantic_assertion_contract() -> None:
    """API-only correction metadata must not leak into the finite Core payload."""

    class RecordingCore(FakeSemanticCoreClient):
        def __init__(self) -> None:
            self.body: object | None = None

        async def request(
            self,
            context: TrustedRequestContext,
            method: str,
            path: str,
            body: object | None = None,
            key: str | None = None,
        ) -> object:
            self.body = body
            return {
                "requestId": context.request_id,
                "candidateId": "cand-01",
                "decision": "confirmed",
                "assertedItemId": "req-01",
                "_projecta_http_status": 201,
            }

    core = RecordingCore()
    app = create_app(_make_settings("test-secret"), core)
    headers = app_headers() | {"Idempotency-Key": "confirm-01"}
    body = {
        "assertion": {
            "type": "Requirement",
            "label": "Confirm address",
            "validFrom": "2026-07-31",
        }
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/candidates/cand-01/confirmations", headers=headers, json=body
        )

    assert response.status_code == 201
    assert core.body == {"assertion": body["assertion"]}


async def test_capture_rejects_mismatched_evidence_before_downstream_call() -> None:
    """An evidence range that does not reproduce segment text is invalid input."""
    app = create_app(_make_settings("test-secret"), FakeSemanticCoreClient())
    headers = app_headers() | {"Idempotency-Key": "capture-02"}
    body = {
        "rawText": "Add address confirmation.",
        "segments": [{"type": "requirement", "startOffset": 0, "endOffset": 3, "text": "Bad"}],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", headers=headers, json=body)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REQUEST"


async def test_capture_normalizes_line_endings_and_preserves_replay_status() -> None:
    """The forwarded model is canonical and a Core replay remains an HTTP 200."""

    class RecordingCore(FakeSemanticCoreClient):
        def __init__(self) -> None:
            self.captured_request: CaptureRequest | None = None

        async def capture(
            self, context: TrustedRequestContext, key: str, request: CaptureRequest
        ) -> CaptureResponse:
            self.captured_request = request
            result = await super().capture(context, key, request)
            result.replayed = True
            return result

    core = RecordingCore()
    app = create_app(_make_settings("test-secret"), core)
    headers = app_headers() | {"Idempotency-Key": "capture-03"}
    body = {
        "rawText": "Confirm address.\r\nTax timeout.",
        "segments": [
            {"type": "requirement", "startOffset": 0, "endOffset": 16, "text": "Confirm address."},
            {"type": "risk", "startOffset": 17, "endOffset": 29, "text": "Tax timeout."},
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", headers=headers, json=body)
    assert response.status_code == 200
    assert core.captured_request is not None
    assert core.captured_request.raw_text == "Confirm address.\nTax timeout."
    assert "replayed" not in response.json()


async def test_downstream_errors_are_sanitized_and_keep_request_id() -> None:
    """Store URLs and Core internals must never cross the public API boundary."""

    class FailingCore(FakeSemanticCoreClient):
        async def capture(
            self, context: TrustedRequestContext, key: str, request: CaptureRequest
        ) -> CaptureResponse:
            raise SemanticCoreProblem(500, "INTERNAL_ERROR", "Fuseki http://private-store/graph")

    app = create_app(_make_settings("test-secret"), FailingCore())
    headers = app_headers() | {"Idempotency-Key": "capture-04"}
    body = {
        "rawText": "Confirm address.",
        "segments": [
            {"type": "requirement", "startOffset": 0, "endOffset": 16, "text": "Confirm address."}
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/quick-notes", headers=headers, json=body)
    assert response.status_code == 503
    assert response.json()["requestId"] == "req-01"
    assert "private-store" not in response.text


async def test_http_client_maps_connect_error_to_contract_unavailable() -> None:
    """Transport failures never escape as framework-generated 500 responses."""

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("downstream unavailable", request=request)

    client = HttpSemanticCoreClient("http://semantic-core", httpx.MockTransport(handler))
    app = create_app(_make_settings("test-secret"), client)
    headers = app_headers() | {"Idempotency-Key": "capture-connect-error"}
    body = {
        "rawText": "A",
        "segments": [{"type": "task", "startOffset": 0, "endOffset": 1, "text": "A"}],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as request_client:
        response = await request_client.post("/v1/quick-notes", headers=headers, json=body)
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "SEMANTIC_CONTRACT_UNAVAILABLE"


async def test_http_client_maps_non_json_success_to_contract_unavailable() -> None:
    """A successful HTTP status with a non-JSON body is still a contract failure."""

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    client = HttpSemanticCoreClient("http://semantic-core", httpx.MockTransport(handler))
    app = create_app(_make_settings("test-secret"), client)
    headers = app_headers() | {"Idempotency-Key": "capture-invalid-response"}
    body = {
        "rawText": "A",
        "segments": [{"type": "task", "startOffset": 0, "endOffset": 1, "text": "A"}],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as request_client:
        response = await request_client.post("/v1/quick-notes", headers=headers, json=body)
    assert response.status_code == 503
    assert response.json()["code"] == "SEMANTIC_CONTRACT_UNAVAILABLE"
