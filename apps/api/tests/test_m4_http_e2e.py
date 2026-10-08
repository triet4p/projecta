"""HTTP-level M4 contract tests with a deterministic Semantic Core replay."""

from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.main import create_app


class ReplayCore:
    def __init__(self) -> None:
        self.mutations = 0

    async def request(self, context: object, method: str, path: str, body: object | None = None, key: str | None = None) -> object:
        assert method == "GET"
        meta = {"projectionVersion": "m4.v1", "sourceRevision": "e2e-r1", "asOf": "2026-08-04T00:00:00Z", "partial": False, "stale": False}
        citation = {"id": "cite-1", "sourceId": "note-1", "evidenceText": "Use MFA", "startOffset": 0, "endOffset": 7}
        if path.startswith("/v1/retrieval/current-requirements"):
            return {"items": [{"id": "req-1", "type": "Requirement", "label": "Use MFA", "status": "asserted", "citation": citation}], "meta": meta}
        if path.startswith("/v1/retrieval/requirement-history"):
            return {"items": [{"id": "req-old", "type": "Requirement", "label": "Old MFA", "status": "asserted", "citation": citation}, {"id": "req-1", "type": "Requirement", "label": "Use MFA", "status": "asserted", "citation": citation}], "meta": meta}
        if path.startswith("/v1/retrieval/unresolved-blockers"):
            return {"items": [{"id": "blocker-1", "type": "UnresolvedBlocker", "label": "Open tax question", "status": "inferred", "citation": citation, "derivation": {"ruleId": "m4.unresolved-dependency", "ruleVersion": "1", "inputIds": ["q-1", "task-1"]}}], "meta": meta}
        raise AssertionError(path)


async def test_m4_http_answers_history_and_blocker_without_mutation() -> None:
    settings = Settings(
        _env_file=None,
        runtime_mode="headless",
        trusted_context_secret="test-secret",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://system-test.invalid",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="replay:m4",
    )
    core = ReplayCore()
    app = create_app(settings=settings, semantic_client=core)  # type: ignore[arg-type]
    headers = {"X-Projecta-Project-Id": "checkout", "X-Projecta-Actor-Id": "le", "X-Projecta-Context-Secret": "test-secret", "X-Request-Id": "m4-e2e"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        for question in ("What are the current requirements?", "What changed in requirement req-1?", "What is blocking checkout?"):
            response = await client.post("/v1/project-context/answers", headers=headers, json={"question": question})
            assert response.status_code == 200
            body = response.json()
            assert body["answerVersion"] == "m4.v1"
            assert body["facts"]
            assert body["citations"]
    assert core.mutations == 0
