"""Manual Note review stays source-bound, receipt-only, and fail-closed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedRequestContext, trusted_context
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
    """Minimal Core port that persists a Note and returns its scoped review context."""

    def __init__(self, *, invalid_span: bool = False) -> None:
        self.project_id = _PROJECT_ID
        self.invalid_span = invalid_span
        self.source_contexts: dict[str, dict[str, object]] = {}
        self.candidate_handle = ""
        self.capture_count = 0
        self.model_calls = 0
        self.assertion_writes: list[str] = []

    async def capture(
        self,
        context: TrustedRequestContext,
        idempotency_key: str,
        request: CaptureRequest,
    ) -> CaptureResponse:
        del idempotency_key
        segment = request.segments[0]
        self.capture_count += 1
        candidate_id = (
            f"https://w3id.org/projecta/data/project/{context.project_id}/candidate/note-1-1"
        )
        self.candidate_handle = "candidate-h-" + sha256(candidate_id.encode()).hexdigest()[:24]
        end_offset = segment.end_offset + (1 if self.invalid_span else 0)
        self.source_contexts[self.candidate_handle] = {
            "projectId": context.project_id,
            "candidateId": "note-1-1",
            "candidateRevision": 1,
            "candidateStatus": "extracted",
            "sourceArtifactId": "note-1",
            "title": request.title,
            "rawText": request.raw_text,
            "evidenceText": segment.text,
            "entityType": "Task",
            "startOffset": segment.start_offset,
            "endOffset": end_offset,
        }
        return CaptureResponse.model_validate(
            {
                "requestId": context.request_id,
                "note": {"id": "note-1", "recordedAt": datetime.now(UTC).isoformat()},
                "candidates": [
                    {
                        "id": candidate_id,
                        "handle": self.candidate_handle,
                        "sourceItemId": "note-1-1",
                        "status": "extracted",
                    }
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
        if path.endswith("/source-context"):
            parts = path.split("/")
            project_id = parts[3]
            candidate_handle = parts[5]
            source = self.source_contexts.get(candidate_handle)
            if source is None or project_id != context.project_id or source["projectId"] != project_id:
                raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not visible in this project")
            return {name: value for name, value in source.items() if name != "projectId"}
        if "/candidates?" in path:
            candidates = []
            for handle, source in self.source_contexts.items():
                if source["projectId"] != context.project_id:
                    continue
                candidates.append(
                    {
                        "handle": handle,
                        "label": source["evidenceText"],
                        "proposedType": source["entityType"],
                        "proposedRelations": [],
                        "validationState": source["candidateStatus"],
                        "lifecycleState": "pending-review",
                        "confidence": 0.0,
                        "evidenceCount": 1,
                    }
                )
            return {"sourceRevision": "source-r1", "stale": False, "candidates": candidates, "hasMore": False}
        if path.endswith("/evidence"):
            return {"items": []}
        if method == "POST" and path.endswith("/validations"):
            candidate_handle = path.split("/")[-2]
            source = self.source_contexts[candidate_handle]
            source["candidateStatus"] = "validated"
            return {"requestId": context.request_id, "conforms": True, "violations": []}
        if method == "POST" and (path.endswith("/confirmations") or path.endswith("/rejections")):
            self.assertion_writes.append(path)
            return {"requestId": context.request_id}
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not visible")


@dataclass(slots=True)
class _Harness:
    app: FastAPI
    core: _ManualCore
    receipts: ReviewDecisionReceiptService
    headers: dict[str, str]
    database: OperationalDatabase

def _make_harness(*, invalid_span: bool = False) -> _Harness:
    core = _ManualCore(invalid_span=invalid_span)
    receipts = ReviewDecisionReceiptService(InMemoryReviewDecisionReceiptRepository())

    class Extraction:
        def record_review_decision(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            request: ReviewDecisionRequest,
        ) -> object:
            del context
            return receipts.record(actor, request)

        def review_decision_history(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            item_kind: str,
            item_handle: str,
        ) -> list[ReviewDecisionReceiptRecord]:
            del context
            return list(receipts.history(actor, item_kind, item_handle))

    database = OperationalDatabase(":memory:")
    app = FastAPI()
    app.add_exception_handler(SemanticCoreProblem, _semantic_problem_response)
    app.state.settings = Settings(
        _env_file=None,
        runtime_mode="experience",
        trusted_context_secret="test-secret",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://provider.example",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="test-model",
    )
    app.state.structured_candidate_edit_store = StructuredCandidateEditStore(database)
    app.include_router(create_router(core, Extraction()))  # type: ignore[arg-type]
    app.dependency_overrides[trusted_context] = lambda: TrustedRequestContext(
        project_id=core.project_id, actor_id="reviewer-1", request_id="req-1"
    )
    return _Harness(
        app=app,
        core=core,
        receipts=receipts,
        headers={"X-Projecta-Selection-Handle": _PROJECT_HANDLE},
        database=database,
    )


def _capture_payload() -> dict[str, object]:
    return {
        "title": "Planning",
        "rawText": _SOURCE_TEXT,
        "segments": [
            {"type": "task", "startOffset": 0, "endOffset": len(_SOURCE_TEXT), "text": _SOURCE_TEXT}
        ],
    }


async def _create_capture_and_get_detail(client: AsyncClient, harness: _Harness) -> dict[str, object]:
    capture_response = await client.post(
        "/v1/quick-notes",
        headers={"Idempotency-Key": "note-create-1"},
        json=_capture_payload(),
    )
    assert capture_response.status_code == 201, capture_response.text
    capture_payload = capture_response.json()
    assert capture_payload["note"]["id"] == "note-1"
    captured_candidate = capture_payload["candidates"][0]
    assert captured_candidate["id"] != captured_candidate["handle"]

    queue_response = await client.get(
        f"/v1/projects/{_PROJECT_HANDLE}/candidates",
        headers=harness.headers,
    )
    assert queue_response.status_code == 200, queue_response.text
    queued_handles = {item["handle"] for item in queue_response.json()["candidates"]}
    assert captured_candidate["handle"] in queued_handles

    detail_path = (
        f"/v1/projects/{_PROJECT_HANDLE}/candidates/{captured_candidate['handle']}/review-detail"
    )
    detail_response = await client.get(detail_path, headers=harness.headers)
    assert detail_response.status_code == 200, detail_response.text
    return detail_response.json()


def _receipt_history(harness: _Harness, project_id: str | None = None) -> list[ReviewDecisionReceiptRecord]:
    selected_project = project_id or harness.core.project_id
    actor = ReviewActorContext(
        project_id=selected_project,
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )
    handle = "eh1_" + sha256(
        f"{selected_project}:review-entity:{harness.core.candidate_handle}".encode()
    ).hexdigest()
    return list(harness.receipts.history(actor, "entity", handle))


@pytest.mark.asyncio
async def test_manual_capture_create_review_receipt_and_confirmation_fail_closed() -> None:
    harness = _make_harness()
    candidate_handle = ""
    async with AsyncClient(transport=ASGITransport(app=harness.app), base_url="http://test") as client:
        detail = await _create_capture_and_get_detail(client, harness)
        candidate_handle = harness.core.candidate_handle
        assert detail["manualCapture"]["mode"] == "human-authored-zero-model"
        assert detail["sourceVersion"]["sourceVersionId"].startswith("sv_")
        anchor = detail["evidence"]["highlights"][0]
        assert (anchor["startOffset"], anchor["endOffset"]) == (0, len(_SOURCE_TEXT))
        assert anchor["utf16End"] == len(_SOURCE_TEXT) + 1

        project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        validation = await client.post(f"{project_path}/validations", headers=harness.headers)
        assert validation.status_code == 200, validation.text
        detail_response = await client.get(f"{project_path}/review-detail", headers=harness.headers)
        detail = detail_response.json()
        anchor = detail["evidence"]["highlights"][0]
        approval = {
            "candidateRevision": detail["candidateRevision"],
            "expectedCandidateRevision": 0,
            "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
            "sourceVersionRevision": detail["sourceVersion"]["revision"],
            "anchorQuoteDigest": anchor["quoteDigest"],
        }

        no_approval = await client.post(
            f"{project_path}/confirmations",
            headers=harness.headers | {"Idempotency-Key": "manual-confirm-before-receipt"},
            json={"assertion": {"type": "Requirement", "label": "ignored", "validFrom": "2026-09-23"}},
        )
        assert no_approval.status_code == 409
        assert no_approval.json()["code"] == "MATERIALIZATION_NOT_AUTHORIZED"

        stale = await client.post(
            f"{project_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "manual-approval-stale"},
            json={**approval, "sourceVersionId": "sv_" + "0" * 64},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "REVIEW_RECEIPT_STALE"
        assert _receipt_history(harness) == []

        accepted = await client.post(
            f"{project_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "manual-approval-1"},
            json=approval,
        )
        assert accepted.status_code == 201, accepted.text
        result = accepted.json()
        assert result["receipt"]["decision"] == "confirm"
        assert result["materializationState"] == "blocked"
        assert result["reasonCode"] == "MATERIALIZATION_NOT_AUTHORIZED"

        replay = await client.post(
            f"{project_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "manual-approval-1"},
            json=approval,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["outcome"] == "replayed"
        assert replay.json()["receipt"]["receiptDigest"] == result["receipt"]["receiptDigest"]

        legacy_confirmation = await client.post(
            f"{project_path}/confirmations",
            headers=harness.headers | {"Idempotency-Key": "legacy-confirm-1"},
            json={"assertion": {"type": "Requirement", "label": "ignored", "validFrom": "2026-09-23"}},
        )
        assert legacy_confirmation.status_code == 409
        assert legacy_confirmation.json()["code"] == "MATERIALIZATION_NOT_AUTHORIZED"

        legacy_rejection = await client.post(
            f"{project_path}/rejections",
            headers=harness.headers | {"Idempotency-Key": "legacy-reject-1"},
            json={"reason": "must use receipt boundary"},
        )
        assert legacy_rejection.status_code == 409
        assert legacy_rejection.json()["code"] == "REVIEW_RECEIPT_REQUIRED"

    assert harness.core.capture_count == 1
    assert harness.core.model_calls == 0
    assert harness.core.assertion_writes == []
    history = _receipt_history(harness)
    assert len(history) == 1
    assert history[0].source_version_revision == 1
    assert history[0].decision == "confirm"


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["reject", "abstain"])
async def test_manual_rejection_and_abstention_are_explicit_receipts_and_not_core_writes(
    decision: str,
) -> None:
    harness = _make_harness()
    async with AsyncClient(transport=ASGITransport(app=harness.app), base_url="http://test") as client:
        detail = await _create_capture_and_get_detail(client, harness)
        candidate_handle = harness.core.candidate_handle
        anchor = detail["evidence"]["highlights"][0]
        project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        if decision == "reject":
            route = f"{project_path}/manual-rejections"
            payload = {
                "candidateRevision": detail["candidateRevision"],
                "expectedCandidateRevision": 0,
                "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
                "sourceVersionRevision": detail["sourceVersion"]["revision"],
                "anchorQuoteDigest": anchor["quoteDigest"],
                "reason": "source does not support this candidate",
            }
        else:
            route = f"{project_path}/abstentions"
            payload = {
                "candidateRevision": detail["candidateRevision"],
                "expectedCandidateRevision": 0,
                "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
                "sourceVersionRevision": detail["sourceVersion"]["revision"],
                "constrainedContractVersion": detail["constrainedContractVersion"],
                "evidenceDigest": detail["evidence"]["digest"],
                "previousDecisionDigest": None,
            }

        recorded = await client.post(
            route,
            headers=harness.headers | {"Idempotency-Key": f"manual-{decision}-1"},
            json=payload,
        )
        assert recorded.status_code == 201, recorded.text
        body = recorded.json()
        assert body["receipt"]["decision"] == decision
        assert "source does not support this candidate" not in json.dumps(body)

        replay = await client.post(
            route,
            headers=harness.headers | {"Idempotency-Key": f"manual-{decision}-1"},
            json=payload,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["outcome"] == "replayed"
        assert replay.json()["receipt"]["receiptDigest"] == body["receipt"]["receiptDigest"]
        if decision == "reject":
            conflicting_route = f"{project_path}/abstentions"
            conflicting_payload = {
                "candidateRevision": detail["candidateRevision"],
                "expectedCandidateRevision": 0,
                "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
                "sourceVersionRevision": detail["sourceVersion"]["revision"],
                "constrainedContractVersion": detail["constrainedContractVersion"],
                "evidenceDigest": detail["evidence"]["digest"],
                "previousDecisionDigest": None,
            }
        else:
            conflicting_route = f"{project_path}/manual-rejections"
            conflicting_payload = {
                "candidateRevision": detail["candidateRevision"],
                "expectedCandidateRevision": 0,
                "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
                "sourceVersionRevision": detail["sourceVersion"]["revision"],
                "anchorQuoteDigest": anchor["quoteDigest"],
                "reason": "conflicting second decision",
            }
        conflict = await client.post(
            conflicting_route,
            headers=harness.headers | {"Idempotency-Key": "conflicting-decision"},
            json=conflicting_payload,
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "REVIEW_RECEIPT_STALE"


        legacy_rejection = await client.post(
            f"{project_path}/rejections",
            headers=harness.headers | {"Idempotency-Key": "legacy-reject-1"},
            json={"reason": "must use receipt boundary"},
        )
        assert legacy_rejection.status_code == 409
        assert legacy_rejection.json()["code"] == "REVIEW_RECEIPT_REQUIRED"

    assert harness.core.capture_count == 1
    assert harness.core.model_calls == 0
    assert harness.core.assertion_writes == []
    history = _receipt_history(harness)
    assert len(history) == 1
    assert history[0].decision == decision


@pytest.mark.asyncio
async def test_invalid_stale_and_cross_project_manual_sources_fail_closed() -> None:
    invalid = _make_harness(invalid_span=True)
    async with AsyncClient(transport=ASGITransport(app=invalid.app), base_url="http://test") as client:
        capture = await client.post(
            "/v1/quick-notes",
            headers={"Idempotency-Key": "note-create-1"},
            json=_capture_payload(),
        )
        assert capture.status_code == 201
        candidate_handle = invalid.core.candidate_handle
        project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        detail = await client.get(f"{project_path}/review-detail", headers=invalid.headers)
        assert detail.status_code == 409
        assert detail.json()["code"] == "MANUAL_CAPTURE_INVALID"

        approval = await client.post(
            f"{project_path}/manual-approvals",
            headers=invalid.headers | {"Idempotency-Key": "invalid-anchor-1"},
            json={
                "candidateRevision": 1,
                "expectedCandidateRevision": 0,
                "sourceVersionId": "sv_" + "0" * 64,
                "sourceVersionRevision": 1,
                "anchorQuoteDigest": "sha256:" + "0" * 64,
            },
        )
        assert approval.status_code == 409
        assert approval.json()["code"] == "MANUAL_CAPTURE_INVALID"
    assert _receipt_history(invalid) == []
    assert invalid.core.assertion_writes == []

    cross_project = _make_harness()
    async with AsyncClient(
        transport=ASGITransport(app=cross_project.app), base_url="http://test"
    ) as client:
        await _create_capture_and_get_detail(client, cross_project)
        candidate_handle = cross_project.core.candidate_handle
        cross_project.core.project_id = "project-beta"
        beta_handle = "project-h-beta123456"
        request = await client.post(
            f"/v1/projects/{beta_handle}/candidates/{candidate_handle}/manual-approvals",
            headers={"X-Projecta-Selection-Handle": beta_handle, "Idempotency-Key": "cross-project-1"},
            json={
                "candidateRevision": 1,
                "expectedCandidateRevision": 0,
                "sourceVersionId": "sv_" + "0" * 64,
                "sourceVersionRevision": 1,
                "anchorQuoteDigest": "sha256:" + "0" * 64,
            },
        )
        assert request.status_code == 404
        assert request.json()["code"] == "RESOURCE_NOT_FOUND"
    assert _receipt_history(cross_project, "project-beta") == []
    assert cross_project.core.assertion_writes == []


@pytest.mark.asyncio
async def test_duplicate_occurrence_anchor_stays_selected_and_stale_source_cannot_add_receipt() -> None:
    harness = _make_harness()
    raw_text = "Plan and Plan"
    selected_start = len("Plan and ")
    async with AsyncClient(transport=ASGITransport(app=harness.app), base_url="http://test") as client:
        capture = await client.post(
            "/v1/quick-notes",
            headers={"Idempotency-Key": "duplicate-occurrence-note"},
            json={
                "title": "Planning",
                "rawText": raw_text,
                "segments": [
                    {
                        "type": "task",
                        "startOffset": selected_start,
                        "endOffset": selected_start + len("Plan"),
                        "text": "Plan",
                    }
                ],
            },
        )
        assert capture.status_code == 201, capture.text
        candidate_handle = harness.core.candidate_handle
        candidate_path = (
            f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        )
        detail_response = await client.get(
            f"{candidate_path}/review-detail", headers=harness.headers
        )
        assert detail_response.status_code == 200, detail_response.text
        detail = detail_response.json()
        anchor = detail["evidence"]["highlights"][0]
        assert detail["sourceText"] == raw_text
        assert anchor["quote"] == "Plan"
        assert (anchor["startOffset"], anchor["endOffset"]) == (
            selected_start,
            selected_start + len("Plan"),
        )

        validation = await client.post(
            f"{candidate_path}/validations", headers=harness.headers
        )
        assert validation.status_code == 200, validation.text
        approval = {
            "candidateRevision": detail["candidateRevision"],
            "expectedCandidateRevision": 0,
            "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
            "sourceVersionRevision": detail["sourceVersion"]["revision"],
            "anchorQuoteDigest": anchor["quoteDigest"],
        }
        accepted = await client.post(
            f"{candidate_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "duplicate-occurrence-approval"},
            json=approval,
        )
        assert accepted.status_code == 201, accepted.text

        harness.core.source_contexts[candidate_handle]["rawText"] = raw_text + " revised"
        stale = await client.post(
            f"{candidate_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "stale-occurrence-approval"},
            json=approval,
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "REVIEW_RECEIPT_STALE"

    history = _receipt_history(harness)
    assert len(history) == 1
    assert history[0].receipt_digest == accepted.json()["receipt"]["receiptDigest"]
    assert harness.core.model_calls == 0
    assert harness.core.assertion_writes == []
