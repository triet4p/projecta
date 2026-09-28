"""RM-62 source-first review workbench projection contract tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.context import TrustedRequestContext, trusted_context
from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptService,
    ReviewDecisionRequest,
    ReviewReceiptStaleError,
)
from projecta_api.graph_projection import project_review_detail
from projecta_api.routes import ReviewAbstainRequest, _review_receipt_handle, create_router
from projecta_api.semantic_core import SemanticCoreProblem


def _payload() -> dict[str, object]:
    return {
        "sourceRevision": "source-r12",
        "stale": False,
        "candidate": {
            "label": "Renewal requirement",
            "proposedType": "Requirement",
            "validationState": "validated",
            "lifecycleState": "pending-review",
            "confidence": 0.82,
            "candidateRevision": 3,
            "sourceText": "Renewal requirement is reviewed before release.",
            "sourceVersion": {
                "revision": 12,
                "canonicalizationVersion": "source.canonical.v1",
                "coordinateSystemVersion": "unicode.codepoint.v1",
                "canonicalDigest": "sha256:" + "a" * 64,
            },
            "anchors": [
                {
                    "kind": "evidence",
                    "startOffset": 0,
                    "endOffset": 20,
                    "displayStartOffset": 0,
                    "displayEndOffset": 20,
                    "utf16Start": 0,
                    "utf16End": 20,
                    "quote": "Renewal requirement",
                    "quoteDigest": "sha256:" + "b" * 64,
                }
            ],
            "evidence": {"status": "selected", "digest": "sha256:" + "c" * 64},
            "uncertaintyReasons": ["LOW_CONFIDENCE"],
            "reviewReceipt": {
                "state": "not-recorded",
                "candidateRevision": 3,
                "sourceVersionRevision": 12,
            },
        },
    }


def test_projection_is_source_first_and_preserves_anchor_display_mappings() -> None:
    result = project_review_detail(
        _payload(), "req-1", "project-h-abc12345", "candidate-h-12345678"
    )
    assert result.detail_version == "review-workbench.v1"
    assert result.project_scope == "selected"
    assert result.source_version.revision == 12
    assert result.evidence.status == "selected"
    assert result.evidence.highlights[0].utf16_end == 20
    assert result.evidence.highlights[0].quote == "Renewal requirement"
    assert result.review_receipt.state == "not-recorded"


def test_invalid_anchor_is_quarantined_and_cannot_present_a_decision_ready_state() -> None:
    payload = _payload()
    candidate = payload["candidate"]
    assert isinstance(candidate, dict)
    candidate["anchors"] = [{"kind": "evidence", "startOffset": 9, "endOffset": 2}]
    result = project_review_detail(payload, "req-2", "project-h-abc12345", "candidate-h-12345678")
    assert result.quarantined is True
    assert result.abstain_reason == "INVALID_SOURCE_ANCHOR"
    assert "INVALID_SOURCE_ANCHOR" in result.uncertainty_reasons


def test_abstain_receipt_is_project_scoped_idempotent_and_stale_safe() -> None:
    source_id = "sv_" + "a" * 64
    request = ReviewAbstainRequest.model_validate(
        {
            "candidateRevision": 1,
            "expectedCandidateRevision": 0,
            "sourceVersionId": source_id,
            "sourceVersionRevision": 1,
            "constrainedContractVersion": "constrained-relation.v1",
            "evidenceDigest": None,
            "previousDecisionDigest": None,
        }
    )
    repository = InMemoryReviewDecisionReceiptRepository()
    service = ReviewDecisionReceiptService(repository)
    actor = ReviewActorContext(
        project_id="project-alpha",
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )
    receipt_request = ReviewDecisionRequest(
        projectId="project-alpha",
        itemKind="entity",
        itemHandle=_review_receipt_handle("project-alpha", "candidate-raw-1"),
        candidateRevision=request.candidate_revision,
        expectedCandidateRevision=request.expected_candidate_revision,
        sourceVersionId=request.source_version_id,
        sourceVersionRevision=request.source_version_revision,
        constrainedContractVersion=request.constrained_contract_version,
        evidenceDigest=request.evidence_digest,
        previousDecisionDigest=request.previous_decision_digest,
        idempotencyKey="abstain-1",
        decision="abstain",
    )
    first = service.record(actor, receipt_request)
    replay = service.record(actor, receipt_request)
    assert first.outcome == "accepted"
    assert replay.outcome == "replayed"
    assert replay.receipt_digest == first.receipt_digest
    with pytest.raises(ReviewReceiptStaleError):
        service.record(
            actor,
            receipt_request.model_copy(
                update={
                    "candidate_revision": 1,
                    "expected_candidate_revision": 0,
                    "idempotency_key": "abstain-stale",
                    "previous_decision_digest": first.receipt_digest,
                }
            ),
        )
    assert len(service.history(actor, "entity", receipt_request.item_handle)) == 1


@pytest.mark.asyncio
async def test_abstain_route_returns_receipt_and_replays_without_mutation() -> None:
    project_id = "project-alpha"
    project_handle = "project-h-abc12345"
    raw_candidate = "candidate-core-1"
    candidate_handle = (
        "candidate-h-" + __import__("hashlib").sha256(raw_candidate.encode()).hexdigest()[:24]
    )
    source_id = "sv_" + "d" * 64
    receipt_service = ReviewDecisionReceiptService(InMemoryReviewDecisionReceiptRepository())

    class Core:
        async def request(
            self,
            context: object,
            method: str,
            path: str,
            body: object | None = None,
            key: str | None = None,
        ) -> object:
            del context, method, body, key
            if path.endswith("/source-context"):
                raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not a manual candidate")
            if "/candidates?" in path:
                return {
                    "sourceRevision": "source-r1",
                    "stale": False,
                    "candidates": [
                        {
                            "handle": raw_candidate,
                            "candidateRevision": 1,
                            "sourceVersion": {"id": source_id, "revision": 1},
                            "evidence": {"digest": "sha256:" + "e" * 64},
                            "constrainedContractVersion": "constrained-relation.v1",
                        }
                    ],
                    "hasMore": False,
                }
            return {"items": []}

    class Extraction:
        def record_review_decision(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            request: ReviewDecisionRequest,
        ):
            return receipt_service.record(actor, request)

        def review_decision_history(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            item_kind: str,
            item_handle: str,
        ):
            return receipt_service.history(actor, item_kind, item_handle)

    app = FastAPI()
    app.state.settings = Settings(
        _env_file=None,
        runtime_mode="experience",
        trusted_context_secret="test-secret",
        PROJECTA_LLM_TYPE="openai-response",
        PROJECTA_LLM_BASE_URL="https://provider.example",
        PROJECTA_LLM_API_KEY="test-key",
        PROJECTA_LLM_MODEL="test-model",
    )
    app.include_router(create_router(Core(), Extraction()))  # type: ignore[arg-type]
    app.dependency_overrides[trusted_context] = lambda: TrustedRequestContext(
        project_id=project_id, actor_id="reviewer-1", request_id="req-abstain"
    )
    headers = {
        "X-Projecta-Selection-Handle": project_handle,
        "Idempotency-Key": "abstain-route-1",
    }
    payload = {
        "candidateRevision": 1,
        "expectedCandidateRevision": 0,
        "sourceVersionId": source_id,
        "sourceVersionRevision": 1,
        "constrainedContractVersion": "constrained-relation.v1",
        "evidenceDigest": "sha256:" + "e" * 64,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            f"/v1/projects/{project_handle}/candidates/{candidate_handle}/abstentions",
            headers=headers,
            json=payload,
        )
        replay = await client.post(
            f"/v1/projects/{project_handle}/candidates/{candidate_handle}/abstentions",
            headers=headers,
            json=payload,
        )
    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert first.json()["receipt"]["decision"] == "abstain"
    assert replay.json()["outcome"] == "replayed"
    assert replay.json()["receipt"]["receiptDigest"] == first.json()["receipt"]["receiptDigest"]
    actor = ReviewActorContext(
        project_id=project_id,
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )
    assert (
        len(
            receipt_service.history(
                actor, "entity", _review_receipt_handle(project_id, raw_candidate)
            )
        )
        == 1
    )
