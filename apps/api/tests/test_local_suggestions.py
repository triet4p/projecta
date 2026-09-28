"""On-demand local suggestions stay behind confirmed receipts and bounded budgets."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedRequestContext, trusted_context
from projecta_api.extraction import local_suggestions as local_suggestions_module
from projecta_api.extraction.local_suggestion_store import (
    LocalSuggestionKey,
    LocalSuggestionRepository,
    LocalSuggestionStoreConflict,
)
from projecta_api.extraction.local_suggestions import (
    LocalSuggestionError,
    LocalSuggestionGateway,
    LocalSuggestionModelOutput,
    LocalSuggestionService,
    LocalSuggestionTarget,
    OllamaLocalSuggestionGateway,
    _validate_model_proposal,
)
from projecta_api.extraction.manual_capture import resolve_manual_capture
from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptRecord,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
)
from projecta_api.models import CaptureRequest, CaptureResponse
from projecta_api.routes import create_router
from projecta_api.semantic_core import SemanticCoreProblem
from projecta_api.structured_candidate_store import StructuredCandidateEditStore

_PROJECT_ID = "project-alpha"
_PROJECT_HANDLE = "project-h-abc12345"
_SOURCE_TEXT = "Plan 🚀 rollout"


async def _semantic_problem_response(request: object, error: SemanticCoreProblem) -> JSONResponse:
    del request
    return JSONResponse({"code": error.code}, status_code=error.status_code)


class _ManualCore:
    def __init__(self) -> None:
        self.source_contexts: dict[str, dict[str, object]] = {}
        self.candidate_ids: dict[str, str] = {}
        self.candidate_handle = ""
        self.capture_count = 0
        self.assertion_writes: list[str] = []

    def add_candidate(
        self,
        candidate_id: str,
        *,
        entity_type: str,
        evidence_text: str,
        start_offset: int,
        end_offset: int,
        project_id: str = _PROJECT_ID,
    ) -> str:
        raw_id = f"https://w3id.org/projecta/data/project/{project_id}/candidate/{candidate_id}"
        handle = "candidate-h-" + sha256(raw_id.encode()).hexdigest()[:24]
        self.candidate_ids[handle] = raw_id
        self.source_contexts[handle] = {
            "projectId": project_id,
            "candidateId": candidate_id,
            "candidateRevision": 1,
            "candidateStatus": "extracted",
            "sourceArtifactId": "note-1",
            "title": "Planning",
            "rawText": _SOURCE_TEXT,
            "evidenceText": evidence_text,
            "entityType": entity_type,
            "startOffset": start_offset,
            "endOffset": end_offset,
        }
        return handle
    async def capture(
        self,
        context: TrustedRequestContext,
        idempotency_key: str,
        request: CaptureRequest,
    ) -> CaptureResponse:
        segment = request.segments[0]
        candidate_id = (
            f"https://w3id.org/projecta/data/project/{context.project_id}/candidate/note-1-1"
        )
        self.candidate_handle = self.add_candidate(
            "note-1-1",
            entity_type="Task",
            evidence_text=segment.text,
            start_offset=segment.start_offset,
            end_offset=segment.end_offset,
            project_id=context.project_id,
        )
        self.capture_count += 1
        self.source_contexts[self.candidate_handle]["title"] = request.title
        self.source_contexts[self.candidate_handle]["rawText"] = request.raw_text
        return CaptureResponse.model_validate(
            {
                "requestId": context.request_id,
                "note": {"id": "note-1", "recordedAt": datetime.now(UTC).isoformat()},
                "candidates": [
                    {"id": candidate_id, "sourceItemId": "note-1-1", "status": "extracted"}
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
        del body, key
        if method == "GET" and path.split("?", 1)[0].endswith("/candidates"):
            return {
                "candidates": [
                    {"handle": raw_id}
                    for handle, raw_id in self.candidate_ids.items()
                    if self.source_contexts[handle]["projectId"] == context.project_id
                ]
            }
        if path.endswith("/source-context"):
            candidate_handle = path.split("/")[-2]
            source = self.source_contexts.get(candidate_handle)
            if source is None or source["projectId"] != context.project_id:
                raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not visible")
            return {name: value for name, value in source.items() if name != "projectId"}
        if method == "POST" and path.endswith("/validations"):
            candidate_handle = path.split("/")[-2]
            self.source_contexts[candidate_handle]["candidateStatus"] = "validated"
            return {"requestId": context.request_id, "conforms": True, "violations": []}
        if method == "POST" and path.endswith("/confirmations"):
            self.assertion_writes.append(path)
            return {"requestId": context.request_id}
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not visible")

    async def entity_link_context(
        self, context: TrustedRequestContext, *, limit: int
    ) -> list[dict[str, object]]:
        assert context.project_id == _PROJECT_ID
        assert limit > 0
        return [{"id": "internal-entity-42", "label": "Existing entity", "type": "Task"}]


class _Extraction:
    def __init__(self) -> None:
        self.receipts = ReviewDecisionReceiptService(InMemoryReviewDecisionReceiptRepository())

    def record_review_decision(
        self,
        context: TrustedRequestContext,
        actor: ReviewActorContext,
        request: ReviewDecisionRequest,
    ) -> ReviewDecisionReceiptRecord:
        del context
        return self.receipts.record(actor, request)

    def review_decision_history(
        self,
        context: TrustedRequestContext,
        actor: ReviewActorContext,
        item_kind: str,
        item_handle: str,
    ) -> list[ReviewDecisionReceiptRecord]:
        del context
        return list(self.receipts.history(actor, item_kind, item_handle))


def _make_app(
    gateway: LocalSuggestionGateway | None = None, *, daily_limit: int = 5
) -> tuple[FastAPI, _ManualCore, OperationalDatabase]:
    core = _ManualCore()
    extraction = _Extraction()
    database = OperationalDatabase(":memory:")
    suggestions = LocalSuggestionService(
        LocalSuggestionRepository(database),
        gateway=gateway,
        user_daily_limit=daily_limit,
        project_daily_limit=daily_limit,
    )
    app = FastAPI()
    app.add_exception_handler(SemanticCoreProblem, _semantic_problem_response)
    app.state.settings = Settings(
        _env_file=None,
        runtime_mode="experience",
        trusted_context_secret="test-secret",
    )
    app.state.structured_candidate_edit_store = StructuredCandidateEditStore(database)
    app.include_router(
        create_router(core, extraction, local_suggestions=suggestions)  # type: ignore[arg-type]
    )
    app.dependency_overrides[trusted_context] = lambda: TrustedRequestContext(
        project_id=_PROJECT_ID, actor_id="reviewer-1", request_id="req-local-suggestion"
    )
    return app, core, database


@pytest.mark.asyncio
async def test_suggestion_requires_validated_confirmed_capture_and_never_infers_on_read() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        capture_response = await client.post(
            "/v1/quick-notes",
            headers=headers | {"Idempotency-Key": "capture-1"},
            json={
                "title": "Planning",
                "rawText": _SOURCE_TEXT,
                "segments": [
                    {
                        "type": "task",
                        "startOffset": 0,
                        "endOffset": len(_SOURCE_TEXT),
                        "text": _SOURCE_TEXT,
                    }
                ],
            },
        )
        assert capture_response.status_code == 201, capture_response.text
        candidate_handle = core.candidate_handle
        base = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        suggestion_path = f"{base}/local-suggestions"

        unvalidated = await client.post(
            suggestion_path,
            headers=headers | {"Idempotency-Key": "suggestion-before-validation"},
            json={"retry": False},
        )
        assert unvalidated.status_code == 409
        assert unvalidated.json()["code"] == "LOCAL_SUGGESTION_REQUIRES_VALIDATION"

        validation = await client.post(f"{base}/validations", headers=headers)
        assert validation.status_code == 200, validation.text
        unconfirmed = await client.post(
            suggestion_path,
            headers=headers | {"Idempotency-Key": "suggestion-before-confirmation"},
            json={"retry": False},
        )
        assert unconfirmed.status_code == 409
        assert unconfirmed.json()["code"] == "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION"
        unconfirmed_read = await client.get(suggestion_path, headers=headers)
        assert unconfirmed_read.status_code == 409
        assert unconfirmed_read.json()["code"] == "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION"

        source_context = {
            name: value
            for name, value in core.source_contexts[candidate_handle].items()
            if name != "projectId"
        }
        verified = resolve_manual_capture(_PROJECT_ID, source_context)
        approval = await client.post(
            f"{base}/manual-approvals",
            headers=headers | {"Idempotency-Key": "manual-approval-1"},
            json={
                "candidateRevision": verified.candidate_revision,
                "expectedCandidateRevision": 0,
                "sourceVersionId": verified.source_version.source_version_id,
                "sourceVersionRevision": 1,
                "anchorQuoteDigest": verified.anchor.quote_digest,
            },
        )
        assert approval.status_code == 201, approval.text
        assert approval.json()["materializationState"] == "blocked"

        state = await client.get(suggestion_path, headers=headers)
        assert state.status_code == 200, state.text
        assert state.json()["state"] == "unavailable"
        assert state.json()["modelAvailable"] is False
        assert state.json()["budget"]["userRemaining"] == 5

        unavailable = await client.post(
            suggestion_path,
            headers=headers | {"Idempotency-Key": "suggestion-without-local-runtime"},
            json={"retry": False},
        )
        assert unavailable.status_code == 503
        assert unavailable.json()["code"] == "LOCAL_MODEL_NOT_CONFIGURED"
        metrics_response = await client.get(
            f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
        )
        assert metrics_response.status_code == 200, metrics_response.text
        metrics = metrics_response.json()
        assert metrics["workflowCount"] == 1
        assert metrics["manualWorkflowCount"] == 1
        assert metrics["localInferenceAttemptCount"] == 0
        assert metrics["zeroModelWorkflowCount"] == 1
        assert metrics["reviewReceiptCount"] == 1
        assert metrics["acceptedAssertionCount"] == 0
        assert metrics["costKnownAcceptedAssertionCount"] == 0
        assert metrics["meanLocalInferenceAttemptsPerAcceptedAssertion"] is None
        assert metrics["reviewLatencySampleCount"] == 0
        assert metrics["reviewLatencyMsTotal"] == 0
        assert metrics["workflows"][0]["reviewLatencyMs"] is None
        assert metrics["workflows"][0]["reviewLatencySampleCount"] == 0
        assert metrics["correctionCategories"] == {
            "unchanged": 1,
            "minor": 0,
            "major": 0,
        }
        assert metrics["workflows"][0]["zeroModel"] is True
        assert _SOURCE_TEXT not in json.dumps(metrics)
        assert "reviewer-1" not in json.dumps(metrics)
        assert core.capture_count == 1
        assert core.assertion_writes == []

    database.close()


def test_suggestion_retries_consume_budgets_and_replays_do_not() -> None:
    database = OperationalDatabase(":memory:")
    repository = LocalSuggestionRepository(database)
    now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    key = LocalSuggestionKey(
        project_id="project-alpha",
        source_version_id="sv_" + "a" * 64,
        source_version_revision=1,
        item_handle="candidate-h-" + "b" * 24,
        item_revision=1,
        evidence_digest="sha256:" + "c" * 64,
    )

    first = repository.reserve(
        key,
        "reviewer-1",
        "attempt-1",
        retry=False,
        now=now,
        user_limit=2,
        project_limit=2,
    )
    assert first.state == "reserved"
    assert first.attempt_digest is not None
    assert (first.budget.user_remaining, first.budget.project_remaining) == (1, 1)

    replay = repository.reserve(
        key,
        "reviewer-1",
        "attempt-1",
        retry=False,
        now=now,
        user_limit=2,
        project_limit=2,
    )
    assert replay.state == "in-progress"
    assert (replay.budget.user_remaining, replay.budget.project_remaining) == (1, 1)
    with pytest.raises(LocalSuggestionStoreConflict):
        repository.reserve(
            key,
            "reviewer-1",
            "attempt-1",
            retry=True,
            now=now,
            user_limit=2,
            project_limit=2,
        )

    repository.fail(key, first.attempt_digest, "local_runtime_unavailable", now=now)
    retry = repository.reserve(
        key,
        "reviewer-1",
        "attempt-2",
        retry=True,
        now=now,
        user_limit=2,
        project_limit=2,
    )
    assert retry.state == "reserved"
    assert (retry.budget.user_remaining, retry.budget.project_remaining) == (0, 0)
    assert retry.attempt_digest is not None
    repository.fail(key, retry.attempt_digest, "local_runtime_unavailable", now=now)

    exhausted = repository.reserve(
        key,
        "reviewer-1",
        "attempt-3",
        retry=True,
        now=now,
        user_limit=2,
        project_limit=2,
    )
    assert exhausted.state == "budget-exhausted"
    assert (exhausted.budget.user_remaining, exhausted.budget.project_remaining) == (0, 0)
    database.close()


def test_model_output_is_strict_and_item_proposals_stay_in_confirmed_quote() -> None:
    grounded = LocalSuggestionModelOutput.model_validate(
        {"kind": "item", "itemText": "Plan", "entityType": "Task"}
    )
    proposal = _validate_model_proposal(grounded, (), _SOURCE_TEXT)
    assert proposal.item_text == "Plan"

    unsupported = LocalSuggestionModelOutput.model_validate(
        {"kind": "item", "itemText": "Unmentioned workstream", "entityType": "Task"}
    )
    with pytest.raises(LocalSuggestionError):
        _validate_model_proposal(unsupported, (), _SOURCE_TEXT)

    with pytest.raises(ValueError):
        LocalSuggestionModelOutput.model_validate(
            {
                "kind": "item",
                "itemText": "Plan",
                "entityType": "Task",
                "globalId": "https://example.test/entity/1",
            }
        )

    link = LocalSuggestionModelOutput.model_validate(
        {"kind": "link", "targetLabel": "EXISTING ENTITY"}
    )
    target = LocalSuggestionTarget(handle="entity-h-0123456789abcdef01234567", label="Existing entity")
    linked = _validate_model_proposal(link, (target,), _SOURCE_TEXT)
    assert linked.target_handle == target.handle
    with pytest.raises(LocalSuggestionError):
        _validate_model_proposal(link, (target, target), _SOURCE_TEXT)


class _ControlledOllamaGateway:
    """A real loopback HTTP peer returning predetermined Ollama proposals."""

    def __init__(self, *outputs: dict[str, object]) -> None:
        self._outputs = list(outputs)
        self.requests: list[dict[str, object]] = []
        self._server: asyncio.AbstractServer | None = None

    async def start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        address = self._server.sockets[0].getsockname()
        monkeypatch.setattr(
            local_suggestions_module,
            "_LOCAL_OLLAMA_GENERATE_URL",
            f"http://127.0.0.1:{address[1]}/api/generate",
        )

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            content_length = next(
                int(line.split(b":", 1)[1].strip())
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            request_body = json.loads(await reader.readexactly(content_length))
            if not isinstance(request_body, dict) or not self._outputs:
                raise ValueError("unexpected Ollama request")
            self.requests.append(request_body)
            response_body = json.dumps(
                {"response": json.dumps(self._outputs.pop(0), ensure_ascii=False)}
            ).encode("utf-8")
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                + f"Content-Length: {len(response_body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + response_body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


async def _capture_confirmed_suggestion_path(
    client: AsyncClient, core: _ManualCore, headers: dict[str, str]
) -> str:
    capture_response = await client.post(
        "/v1/quick-notes",
        headers=headers | {"Idempotency-Key": "capture-for-local-suggestion"},
        json={
            "title": "Planning",
            "rawText": _SOURCE_TEXT,
            "segments": [
                {
                    "type": "task",
                    "startOffset": 0,
                    "endOffset": len(_SOURCE_TEXT),
                    "text": _SOURCE_TEXT,
                }
            ],
        },
    )
    assert capture_response.status_code == 201, capture_response.text
    candidate_handle = core.candidate_handle
    base = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
    validation = await client.post(f"{base}/validations", headers=headers)
    assert validation.status_code == 200, validation.text

    verified = resolve_manual_capture(
        _PROJECT_ID,
        {
            name: value
            for name, value in core.source_contexts[candidate_handle].items()
            if name != "projectId"
        },
    )
    approval = await client.post(
        f"{base}/manual-approvals",
        headers=headers | {"Idempotency-Key": "manual-approval-for-local-suggestion"},
        json={
            "candidateRevision": verified.candidate_revision,
            "expectedCandidateRevision": 0,
            "sourceVersionId": verified.source_version.source_version_id,
            "sourceVersionRevision": 1,
            "anchorQuoteDigest": verified.anchor.quote_digest,
        },
    )
    assert approval.status_code == 201, approval.text
    assert approval.json()["materializationState"] == "blocked"
    return f"{base}/local-suggestions"

async def _approve_manual_candidate(
    client: AsyncClient,
    core: _ManualCore,
    headers: dict[str, str],
    candidate_handle: str,
    key_suffix: str,
) -> None:
    base = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
    validation = await client.post(f"{base}/validations", headers=headers)
    assert validation.status_code == 200, validation.text
    verified = resolve_manual_capture(
        _PROJECT_ID,
        {
            name: value
            for name, value in core.source_contexts[candidate_handle].items()
            if name != "projectId"
        },
    )
    approval = await client.post(
        f"{base}/manual-approvals",
        headers=headers | {"Idempotency-Key": f"relation-approval-{key_suffix}"},
        json={
            "candidateRevision": verified.candidate_revision,
            "expectedCandidateRevision": 0,
            "sourceVersionId": verified.source_version.source_version_id,
            "sourceVersionRevision": 1,
            "anchorQuoteDigest": verified.anchor.quote_digest,
        },
    )
    assert approval.status_code == 201, approval.text
    assert approval.json()["materializationState"] == "blocked"


async def _capture_confirmed_relation_pair(
    client: AsyncClient, core: _ManualCore, headers: dict[str, str]
) -> tuple[str, str]:
    captured = await client.post(
        "/v1/quick-notes",
        headers=headers | {"Idempotency-Key": "capture-relation-source"},
        json={
            "title": "Planning",
            "rawText": _SOURCE_TEXT,
            "segments": [
                {"type": "task", "startOffset": 0, "endOffset": 4, "text": "Plan"}
            ],
        },
    )
    assert captured.status_code == 201, captured.text
    source_handle = core.candidate_handle
    target_handle = core.add_candidate(
        "note-1-2",
        entity_type="Requirement",
        evidence_text="rollout",
        start_offset=7,
        end_offset=14,
    )
    await _approve_manual_candidate(client, core, headers, source_handle, "source")
    await _approve_manual_candidate(client, core, headers, target_handle, "target")
    return source_handle, target_handle


@pytest.mark.asyncio
async def test_local_suggestion_uses_controlled_ollama_http_and_persists_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama = _ControlledOllamaGateway(
        {"kind": "item", "itemText": "Plan", "entityType": "Task"}
    )
    await ollama.start(monkeypatch)
    app, core, database = _make_app(
        OllamaLocalSuggestionGateway("test-local-model"), daily_limit=1
    )
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = await _capture_confirmed_suggestion_path(client, core, headers)
            before = await client.get(path, headers=headers)
            assert before.status_code == 200, before.text
            assert before.json()["state"] == "ready"
            assert before.json()["budget"]["userRemaining"] == 1
            assert ollama.requests == []

            proposal_response = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "suggestion-proposal-1"},
                json={"retry": False},
            )
            assert proposal_response.status_code == 200, proposal_response.text
            proposal = proposal_response.json()
            assert proposal["state"] == "proposed"
            assert proposal["suggestion"]["kind"] == "item"
            assert proposal["suggestion"]["itemText"] == "Plan"
            assert proposal["suggestion"]["revision"] == 1
            assert proposal["suggestion"]["materializationState"] == "blocked"
            assert proposal["budget"]["userRemaining"] == 0
            assert len(ollama.requests) == 1

            gateway_request = ollama.requests[0]
            assert gateway_request["model"] == "test-local-model"
            assert gateway_request["stream"] is False
            assert isinstance(gateway_request["prompt"], str)
            assert "Planning" in gateway_request["prompt"]
            assert _SOURCE_TEXT in gateway_request["prompt"]
            assert "internal-entity-42" not in gateway_request["prompt"]
            schema = gateway_request["format"]
            assert isinstance(schema, dict)
            assert schema["additionalProperties"] is False
            variants = schema["anyOf"]
            assert isinstance(variants, list)
            required_by_kind = {
                variant["properties"]["kind"]["const"]: set(variant["required"])
                for variant in variants
            }
            assert required_by_kind == {
                "item": {"kind", "itemText", "entityType"},
                "type": {"kind", "entityType"},
                "link": {"kind", "targetLabel"},
                "abstain": {"kind", "abstentionCode"},
                "relation": {"kind", "predicate"},
            }

            persisted = await client.get(path, headers=headers)
            assert persisted.status_code == 200, persisted.text
            assert persisted.json()["state"] == "proposed"
            assert persisted.json()["suggestion"] == proposal["suggestion"]
            assert persisted.json()["budget"]["userRemaining"] == 0

            replay = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "suggestion-proposal-1"},
                json={"retry": False},
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["suggestion"] == proposal["suggestion"]
            assert replay.json()["budget"]["userRemaining"] == 0
            assert len(ollama.requests) == 1
            metrics_response = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert metrics_response.status_code == 200, metrics_response.text
            metrics = metrics_response.json()
            assert metrics["workflowCount"] == 1
            assert metrics["manualWorkflowCount"] == 1
            assert metrics["localRequestCount"] == 1
            assert metrics["localInferenceAttemptCount"] == 1
            assert metrics["zeroModelWorkflowCount"] == 0
            assert metrics["reviewReceiptCount"] == 1
            assert metrics["acceptedAssertionCount"] == 0
            assert metrics["acceptedAssertions"] == []
            assert metrics["workflows"][0]["workflowMode"] == "mixed"
            assert metrics["workflows"][0]["localInferenceAttempts"] == 1
            metrics_text = json.dumps(metrics)
            assert _SOURCE_TEXT not in metrics_text
            assert "Planning" not in metrics_text
            assert "Plan" not in metrics_text
            with database.transaction() as connection:
                event_rows = connection.execute(
                    "SELECT * FROM authoring_cost_events"
                ).fetchall()
            assert _SOURCE_TEXT not in str(event_rows)
            assert "Planning" not in str(event_rows)
            assert "Plan" not in str(event_rows)
            assert core.assertion_writes == []
    finally:
        await ollama.close()
        database.close()


@pytest.mark.asyncio
async def test_local_suggestion_edit_confirm_receipts_replay_and_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama = _ControlledOllamaGateway(
        {"kind": "item", "itemText": "Plan", "entityType": "Task"}
    )
    await ollama.start(monkeypatch)
    app, core, database = _make_app(OllamaLocalSuggestionGateway("test-local-model"))
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = await _capture_confirmed_suggestion_path(client, core, headers)
            generated = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "suggestion-for-edit-confirm"},
                json={"retry": False},
            )
            assert generated.status_code == 200, generated.text
            suggestion = generated.json()["suggestion"]
            suggestion_id = suggestion["suggestionId"]
            decision_path = f"{path}/{suggestion_id}/decisions"

            edited = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-edit-1"},
                json={
                    "expectedProposalRevision": 1,
                    "decision": "edit",
                    "edit": {"itemText": "Plan 🚀", "entityType": "Task"},
                },
            )
            assert edited.status_code == 200, edited.text
            edit_result = edited.json()
            edit_receipt = edit_result["receipt"]
            assert edit_result["state"] == "edited"
            assert edit_result["suggestion"]["revision"] == 2
            assert edit_result["suggestion"]["itemText"] == "Plan 🚀"
            assert edit_receipt["decision"] == "edit"
            assert edit_receipt["outcome"] == "accepted"
            assert edit_receipt["sequence"] == 1
            assert edit_result["suggestion"]["receiptDigest"] == edit_receipt["receiptDigest"]
            assert edit_result["suggestion"]["materializationState"] == "blocked"

            stale = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-stale-1"},
                json={
                    "expectedProposalRevision": 1,
                    "decision": "reject",
                    "reason": "The proposal changed",
                },
            )
            assert stale.status_code == 409
            assert stale.json()["code"] == "LOCAL_SUGGESTION_STALE"

            confirmed = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-confirm-1"},
                json={"expectedProposalRevision": 2, "decision": "confirm"},
            )
            assert confirmed.status_code == 200, confirmed.text
            confirm_result = confirmed.json()
            confirm_receipt = confirm_result["receipt"]
            assert confirm_result["state"] == "confirmed"
            assert confirm_receipt["decision"] == "confirm"
            assert confirm_receipt["outcome"] == "accepted"
            assert confirm_receipt["sequence"] == 2
            assert confirm_receipt["previousDecisionDigest"] == edit_receipt["receiptDigest"]
            assert confirm_result["suggestion"]["receiptDigest"] == confirm_receipt["receiptDigest"]
            assert confirm_result["suggestion"]["materializationState"] == "blocked"

            replay = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-confirm-1"},
                json={"expectedProposalRevision": 2, "decision": "confirm"},
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["receipt"]["outcome"] == "replayed"
            assert replay.json()["receipt"]["receiptDigest"] == confirm_receipt["receiptDigest"]
            assert replay.json()["receipt"]["sequence"] == 2

            conflict = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-confirm-1"},
                json={
                    "expectedProposalRevision": 2,
                    "decision": "reject",
                    "reason": "Conflicting reuse",
                },
            )
            assert conflict.status_code == 409
            assert conflict.json()["code"] == "LOCAL_SUGGESTION_CONFLICT"

            readback = await client.get(path, headers=headers)
            assert readback.status_code == 200, readback.text
            assert readback.json()["state"] == "confirmed"
            assert readback.json()["suggestion"]["itemText"] == "Plan 🚀"
            assert core.assertion_writes == []
    finally:
        await ollama.close()
        database.close()


@pytest.mark.asyncio
async def test_local_suggestion_rejection_records_and_replays_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama = _ControlledOllamaGateway(
        {"kind": "item", "itemText": "Plan", "entityType": "Task"}
    )
    await ollama.start(monkeypatch)
    app, core, database = _make_app(OllamaLocalSuggestionGateway("test-local-model"))
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            path = await _capture_confirmed_suggestion_path(client, core, headers)
            generated = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "suggestion-for-rejection"},
                json={"retry": False},
            )
            assert generated.status_code == 200, generated.text
            suggestion_id = generated.json()["suggestion"]["suggestionId"]
            decision_path = f"{path}/{suggestion_id}/decisions"
            decision_body = {
                "expectedProposalRevision": 1,
                "decision": "reject",
                "reason": "Insufficient evidence",
            }
            rejected = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-reject-1"},
                json=decision_body,
            )
            assert rejected.status_code == 200, rejected.text
            rejection = rejected.json()
            receipt = rejection["receipt"]
            assert rejection["state"] == "rejected"
            assert receipt["decision"] == "reject"
            assert receipt["outcome"] == "accepted"
            assert receipt["sequence"] == 1
            assert rejection["suggestion"]["receiptDigest"] == receipt["receiptDigest"]
            assert rejection["suggestion"]["materializationState"] == "blocked"

            replay = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "decision-reject-1"},
                json=decision_body,
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["receipt"]["outcome"] == "replayed"
            assert replay.json()["receipt"]["receiptDigest"] == receipt["receiptDigest"]
            assert replay.json()["receipt"]["sequence"] == 1
            assert core.assertion_writes == []
    finally:
        await ollama.close()
        database.close()


@pytest.mark.asyncio
async def test_manual_relation_requires_two_current_confirmations_and_records_rejection() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            source_handle, target_handle = await _capture_confirmed_relation_pair(
                client, core, headers
            )
            base = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{source_handle}"
            targets = await client.get(
                f"{base}/relation-suggestion-targets", headers=headers
            )
            assert targets.status_code == 200, targets.text
            target = next(
                value
                for value in targets.json()["targets"]
                if value["candidateHandle"] == target_handle
            )
            assert "implements" in target["allowedPredicates"]["source-to-target"]
            assert "implements" not in target["allowedPredicates"]["target-to-source"]

            relation_path = f"{base}/relation-suggestions"
            unsupported = await client.post(
                relation_path,
                headers=headers | {"Idempotency-Key": "relation-unsupported-direction"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "target-to-source",
                    "mode": "manual",
                    "predicate": "implements",
                },
            )
            assert unsupported.status_code == 422
            assert unsupported.json()["code"] == "CONTROLLED_RELATION_UNSUPPORTED"

            unconfirmed_handle = core.add_candidate(
                "note-1-3",
                entity_type="Requirement",
                evidence_text="rollout",
                start_offset=7,
                end_offset=14,
            )
            unconfirmed_base = (
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{unconfirmed_handle}"
            )
            validated = await client.post(
                f"{unconfirmed_base}/validations", headers=headers
            )
            assert validated.status_code == 200
            unconfirmed = await client.post(
                relation_path,
                headers=headers | {"Idempotency-Key": "relation-unconfirmed-target"},
                json={
                    "targetCandidateHandle": unconfirmed_handle,
                    "direction": "source-to-target",
                    "mode": "manual",
                    "predicate": "implements",
                },
            )
            assert unconfirmed.status_code == 409
            assert (
                unconfirmed.json()["code"]
                == "CONTROLLED_RELATION_REQUIRES_CONFIRMATION"
            )

            other_project_handle = core.add_candidate(
                "note-foreign",
                entity_type="Requirement",
                evidence_text="rollout",
                start_offset=7,
                end_offset=14,
                project_id="project-beta",
            )
            cross_project = await client.post(
                relation_path,
                headers=headers | {"Idempotency-Key": "relation-cross-project"},
                json={
                    "targetCandidateHandle": other_project_handle,
                    "direction": "source-to-target",
                    "mode": "manual",
                    "predicate": "implements",
                },
            )
            assert cross_project.status_code == 404

            created = await client.post(
                relation_path,
                headers=headers | {"Idempotency-Key": "relation-manual-proposal"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "manual",
                    "predicate": "implements",
                },
            )
            assert created.status_code == 200, created.text
            proposal = created.json()
            assert proposal["state"] == "proposed"
            assert proposal["modelAvailable"] is False
            assert proposal["budget"]["userRemaining"] == 5
            assert proposal["suggestion"]["kind"] == "relation"
            assert proposal["suggestion"]["predicate"] == "implements"
            assert proposal["suggestion"]["direction"] == "source-to-target"
            assert proposal["suggestion"]["materializationState"] == "blocked"
            evidence = proposal["suggestion"]["relationEvidence"]
            assert evidence["outcome"] == "selected"
            assert evidence["materializable"] is True
            assert "quote" not in evidence

            suggestion_id = proposal["suggestion"]["suggestionId"]
            state = await client.get(
                f"{relation_path}/{suggestion_id}", headers=headers
            )
            assert state.status_code == 200, state.text
            assert state.json()["suggestion"] == proposal["suggestion"]
            pair_state = await client.get(
                relation_path,
                params={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "manual",
                    "predicate": "implements",
                },
                headers=headers,
            )
            assert pair_state.status_code == 200, pair_state.text
            assert pair_state.json()["suggestion"] == proposal["suggestion"]

            core.source_contexts[target_handle]["candidateRevision"] = 2
            stale_endpoint = await client.get(
                f"{relation_path}/{suggestion_id}", headers=headers
            )
            assert stale_endpoint.status_code == 409
            assert (
                stale_endpoint.json()["code"]
                == "CONTROLLED_RELATION_REQUIRES_CONFIRMATION"
            )
            core.source_contexts[target_handle]["candidateRevision"] = 1

            decision_path = f"{relation_path}/{suggestion_id}/decisions"
            stale = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "relation-stale-revision"},
                json={"expectedProposalRevision": 2, "decision": "reject"},
            )
            assert stale.status_code == 409
            assert stale.json()["code"] == "CONTROLLED_RELATION_STALE"

            rejected = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "relation-reject"},
                json={
                    "expectedProposalRevision": 1,
                    "decision": "reject",
                    "reason": "The evidence needs another review.",
                },
            )
            assert rejected.status_code == 200, rejected.text
            result = rejected.json()
            receipt = result["receipt"]
            assert result["state"] == "rejected"
            assert result["suggestion"]["receiptDigest"] == receipt["receiptDigest"]
            assert receipt["itemKind"] == "relation"
            assert receipt["decision"] == "reject"
            assert receipt["evidenceDigest"] == proposal["suggestion"]["relationEvidenceDigest"]
            assert receipt["constrainedContractVersion"] == "controlled-relation-suggestion.v1"

            replay = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "relation-reject"},
                json={
                    "expectedProposalRevision": 1,
                    "decision": "reject",
                    "reason": "The evidence needs another review.",
                },
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["receipt"]["outcome"] == "replayed"
            assert replay.json()["receipt"]["receiptDigest"] == receipt["receiptDigest"]
            assert core.assertion_writes == []
    finally:
        database.close()


@pytest.mark.asyncio
async def test_local_relation_model_selects_only_allowlisted_predicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama = _ControlledOllamaGateway({"kind": "relation", "predicate": "implements"})
    await ollama.start(monkeypatch)
    app, core, database = _make_app(OllamaLocalSuggestionGateway("test-relation-model"))
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            source_handle, target_handle = await _capture_confirmed_relation_pair(
                client, core, headers
            )
            base = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{source_handle}"
            path = f"{base}/relation-suggestions"
            generated = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "relation-local-proposal"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "local",
                    "retry": False,
                },
            )
            assert generated.status_code == 200, generated.text
            proposal = generated.json()
            assert proposal["state"] == "proposed"
            assert proposal["suggestion"]["kind"] == "relation"
            assert proposal["suggestion"]["predicate"] == "implements"
            assert proposal["suggestion"]["relationId"].startswith("rel_")
            assert proposal["budget"]["userRemaining"] == 4
            assert len(ollama.requests) == 1

            gateway_request = ollama.requests[0]
            prompt = gateway_request["prompt"]
            assert isinstance(prompt, str)
            model_context = json.loads(prompt.split("INPUT_JSON:\n", 1)[1])
            assert model_context["semanticSourceOccurrence"] == "Plan"
            assert model_context["semanticTargetOccurrence"] == "rollout"
            assert model_context["humanSelectedDirection"] == "source-to-target"
            assert "implements" in model_context["allowedPredicates"]
            for forbidden in (
                source_handle,
                target_handle,
                "relationId",
                "sourceHandle",
                "startOffset",
                "evidenceDigest",
            ):
                assert forbidden not in prompt

            decision_path = f"{path}/{proposal['suggestion']['suggestionId']}/decisions"
            confirmed = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "relation-confirm"},
                json={"expectedProposalRevision": 1, "decision": "confirm"},
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["state"] == "confirmed"
            assert confirmed.json()["receipt"]["decision"] == "confirm"
            replay = await client.post(
                decision_path,
                headers=headers | {"Idempotency-Key": "relation-confirm"},
                json={"expectedProposalRevision": 1, "decision": "confirm"},
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["receipt"]["outcome"] == "replayed"
            assert core.assertion_writes == []
    finally:
        await ollama.close()
        database.close()


@pytest.mark.asyncio
async def test_local_relation_rejects_unsupported_and_model_authored_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama = _ControlledOllamaGateway(
        {"kind": "relation", "predicate": "invented"},
        {"kind": "relation", "predicate": "implements", "relationId": "rel_model"},
        {"kind": "abstain", "abstentionCode": "insufficient_evidence"},
    )
    await ollama.start(monkeypatch)
    app, core, database = _make_app(OllamaLocalSuggestionGateway("test-relation-model"))
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            source_handle, target_handle = await _capture_confirmed_relation_pair(
                client, core, headers
            )
            path = (
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{source_handle}"
                "/relation-suggestions"
            )
            first = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "relation-invalid-predicate"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "local",
                },
            )
            assert first.status_code == 502
            assert first.json()["code"] == "LOCAL_SUGGESTION_INVALID"
            second = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "relation-model-authored-id"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "local",
                    "retry": True,
                },
            )
            assert second.status_code == 502
            assert second.json()["code"] == "LOCAL_SUGGESTION_INVALID"
            abstained = await client.post(
                path,
                headers=headers | {"Idempotency-Key": "relation-model-abstain"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "local",
                    "retry": True,
                },
            )
            assert abstained.status_code == 200, abstained.text
            assert abstained.json()["state"] == "abstained"
            assert abstained.json()["suggestion"]["kind"] == "abstain"
            assert abstained.json()["suggestion"]["targetCandidateHandle"] == target_handle
            state = await client.get(
                f"{path}/{abstained.json()['suggestion']['suggestionId']}",
                headers=headers,
            )
            assert state.status_code == 200, state.text
            assert state.json()["state"] == "abstained"
            assert len(ollama.requests) == 3
            assert core.assertion_writes == []
    finally:
        await ollama.close()
        database.close()


@pytest.mark.asyncio
async def test_manual_candidate_corrections_are_classified_without_copying_values() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _capture_confirmed_suggestion_path(client, core, headers)
            candidate_handle = core.candidate_handle
            edit = await client.post(
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}/edits",
                headers=headers,
                json={"label": "Private corrected label", "expectedRevision": 1},
            )
            assert edit.status_code == 200, edit.text

            response = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert response.status_code == 200, response.text
            metrics = response.json()
            assert metrics["workflowCount"] == 1
            assert metrics["zeroModelWorkflowCount"] == 1
            assert metrics["semanticEditCount"] == 1
            assert metrics["correctionEventCount"] == 2
            assert metrics["correctionCategories"] == {
                "unchanged": 1,
                "minor": 1,
                "major": 0,
            }
            assert "Private corrected label" not in json.dumps(metrics)
            with database.transaction() as connection:
                event_rows = connection.execute(
                    "SELECT * FROM authoring_cost_events"
                ).fetchall()
            assert "Private corrected label" not in str(event_rows)
    finally:
        database.close()

@pytest.mark.asyncio
async def test_manual_date_only_edit_is_counted_but_has_no_category_or_raw_value() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    date_value = "2042-08-16"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _capture_confirmed_suggestion_path(client, core, headers)
            edit = await client.post(
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{core.candidate_handle}/edits",
                headers=headers,
                json={"date": date_value, "expectedRevision": 1},
            )
            assert edit.status_code == 200, edit.text

            response = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert response.status_code == 200, response.text
            metrics = response.json()
            assert metrics["semanticEditCount"] == 1
            assert metrics["correctionEventCount"] == 2
            assert metrics["correctionCategories"] == {
                "unchanged": 1,
                "minor": 0,
                "major": 0,
            }
            assert sum(metrics["correctionCategories"].values()) == 1
            assert date_value not in json.dumps(metrics)

            with database.transaction() as connection:
                event_rows = connection.execute(
                    """SELECT correction_category, correction_dimensions, semantic_edit_count
                       FROM authoring_cost_events WHERE event_type = 'manual_edit'"""
                ).fetchall()
            assert len(event_rows) == 1
            assert event_rows[0]["correction_category"] is None
            assert event_rows[0]["correction_dimensions"] == "[]"
            assert event_rows[0]["semantic_edit_count"] == 1
            assert date_value not in str([dict(row) for row in event_rows])
    finally:
        database.close()


@pytest.mark.asyncio
async def test_manual_date_and_type_edit_uses_major_precedence_without_raw_values() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    date_value = "2042-08-17"
    type_value = "Decision"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await _capture_confirmed_suggestion_path(client, core, headers)
            edit = await client.post(
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{core.candidate_handle}/edits",
                headers=headers,
                json={
                    "date": date_value,
                    "entityType": type_value,
                    "expectedRevision": 1,
                },
            )
            assert edit.status_code == 200, edit.text

            response = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert response.status_code == 200, response.text
            metrics = response.json()
            assert metrics["semanticEditCount"] == 2
            assert metrics["correctionEventCount"] == 2
            assert metrics["correctionCategories"] == {
                "unchanged": 1,
                "minor": 0,
                "major": 1,
            }
            assert sum(metrics["correctionCategories"].values()) == 2
            metrics_text = json.dumps(metrics)
            assert date_value not in metrics_text
            assert type_value not in metrics_text

            with database.transaction() as connection:
                event_rows = connection.execute(
                    """SELECT correction_category, correction_dimensions, semantic_edit_count
                       FROM authoring_cost_events WHERE event_type = 'manual_edit'"""
                ).fetchall()
            assert len(event_rows) == 1
            assert event_rows[0]["correction_category"] == "major"
            assert event_rows[0]["correction_dimensions"] == '["type"]'
            assert event_rows[0]["semantic_edit_count"] == 2
            telemetry_rows = str([dict(row) for row in event_rows])
            assert date_value not in telemetry_rows
            assert type_value not in telemetry_rows
    finally:
        database.close()


@pytest.mark.asyncio
async def test_unknown_manual_relation_predicate_creates_no_proposal() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            source_handle, target_handle = await _capture_confirmed_relation_pair(
                client, core, headers
            )
            relation_path = (
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{source_handle}"
                "/relation-suggestions"
            )
            rejected = await client.post(
                relation_path,
                headers=headers | {"Idempotency-Key": "unsupported-manual-predicate"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "manual",
                    "predicate": "administersAll",
                },
            )
            assert rejected.status_code == 422
            assert rejected.json()["code"] == "CONTROLLED_RELATION_UNSUPPORTED"

            with database.transaction() as connection:
                workflows = connection.execute(
                    "SELECT COUNT(*) FROM local_suggestion_workflows"
                ).fetchone()[0]
            assert workflows == 0
            assert core.assertion_writes == []
    finally:
        database.close()


@pytest.mark.asyncio
async def test_swapped_persisted_relation_endpoints_cannot_be_read_or_confirmed() -> None:
    app, core, database = _make_app()
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            source_handle, target_handle = await _capture_confirmed_relation_pair(
                client, core, headers
            )
            relation_path = (
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/{source_handle}"
                "/relation-suggestions"
            )
            created = await client.post(
                relation_path,
                headers=headers | {"Idempotency-Key": "relation-before-endpoint-mutation"},
                json={
                    "targetCandidateHandle": target_handle,
                    "direction": "source-to-target",
                    "mode": "manual",
                    "predicate": "implements",
                },
            )
            assert created.status_code == 200, created.text
            suggestion = created.json()["suggestion"]
            suggestion_id = suggestion["suggestionId"]

            metrics_before = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert metrics_before.status_code == 200, metrics_before.text

            with database.transaction() as connection:
                row = connection.execute(
                    "SELECT proposal_json FROM local_suggestion_workflows "
                    "WHERE workflow_id = ?",
                    (suggestion_id,),
                ).fetchone()
                assert row is not None
                proposal = json.loads(str(row["proposal_json"]))
                assert proposal["sourceCandidateHandle"] == source_handle
                assert proposal["semanticTargetCandidateHandle"] == target_handle
                proposal["sourceCandidateHandle"], proposal["semanticTargetCandidateHandle"] = (
                    target_handle,
                    source_handle,
                )
                proposal["sourceHandle"], proposal["targetHandle"] = (
                    proposal["targetHandle"],
                    proposal["sourceHandle"],
                )
                connection.execute(
                    "UPDATE local_suggestion_workflows SET proposal_json = ? "
                    "WHERE workflow_id = ?",
                    (
                        json.dumps(proposal, ensure_ascii=False),
                        suggestion_id,
                    ),
                )

            detail = await client.get(
                f"{relation_path}/{suggestion_id}", headers=headers
            )
            assert detail.status_code == 409
            assert detail.json()["code"] == "CONTROLLED_RELATION_STALE"
            confirmation = await client.post(
                f"{relation_path}/{suggestion_id}/decisions",
                headers=headers | {"Idempotency-Key": "swapped-relation-confirm"},
                json={"expectedProposalRevision": 1, "decision": "confirm"},
            )
            assert confirmation.status_code == 409
            assert confirmation.json()["code"] == "CONTROLLED_RELATION_STALE"

            metrics_after = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert metrics_after.status_code == 200, metrics_after.text
            assert (
                metrics_after.json()["reviewReceiptCount"]
                == metrics_before.json()["reviewReceiptCount"]
            )
            assert metrics_after.json()["acceptedAssertionCount"] == 0
            assert core.assertion_writes == []
    finally:
        database.close()


@pytest.mark.asyncio
async def test_unreviewed_local_proposal_cannot_reach_asserted_core(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ollama = _ControlledOllamaGateway(
        {"kind": "item", "itemText": "Plan", "entityType": "Task"}
    )
    await ollama.start(monkeypatch)
    app, core, database = _make_app(OllamaLocalSuggestionGateway("test-unreviewed-model"))
    headers = {"X-Projecta-Selection-Handle": _PROJECT_HANDLE}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            suggestion_path = await _capture_confirmed_suggestion_path(
                client, core, headers
            )
            proposal = await client.post(
                suggestion_path,
                headers=headers | {"Idempotency-Key": "unreviewed-proposal"},
                json={"retry": False},
            )
            assert proposal.status_code == 200, proposal.text
            assert proposal.json()["state"] == "proposed"
            assert proposal.json()["suggestion"]["materializationState"] == "blocked"

            finalization = await client.post(
                f"/v1/projects/{_PROJECT_HANDLE}/candidates/"
                f"{core.candidate_handle}/confirmations",
                headers=headers | {"Idempotency-Key": "unreviewed-finalization"},
                json={
                    "assertion": {
                        "type": "Requirement",
                        "label": "Unreviewed proposal",
                        "validFrom": "2026-09-28",
                    }
                },
            )
            assert finalization.status_code == 409
            assert finalization.json()["code"] == "MATERIALIZATION_NOT_AUTHORIZED"
            assert core.assertion_writes == []

            metrics = await client.get(
                f"/v1/projects/{_PROJECT_HANDLE}/authoring-metrics", headers=headers
            )
            assert metrics.status_code == 200, metrics.text
            assert metrics.json()["acceptedAssertionCount"] == 0
            assert metrics.json()["localInferenceAttemptCount"] == 1
    finally:
        await ollama.close()
        database.close()
