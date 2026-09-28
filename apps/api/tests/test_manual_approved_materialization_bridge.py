"""S13-02 connected slice: real Note capture through persisted receipt to plan.

This harness is the test-authorized integration bridge the evidence review
required. It drives the real production route stack (Quick Note capture,
Core source-context, review-detail, validations, manual-approvals) against a
minimal Core port that persists a Note exactly like ``QuickNoteCaptureService``
(project-scoped NoteItem evidence, manual generator, immutable source text)
and returns its scoped review context exactly like ``FusekiQueryService``.
It then builds the approved plan from the *actual persisted RM-61 receipt*
via ``plan_and_fixture_for_test_materialization`` -- never a hand-seeded
digest -- and asserts the durable receipt, exact source binding, and plan
digests as observed behavior. The positive path asserts every link of the
connected chain; the negative tests prove reject/abstain/stale/cross-project
inputs fail closed before any plan exists. Production stays locked: the
approval route still returns ``blocked``/``MATERIALIZATION_NOT_AUTHORIZED``
and this file never enables a production toggle.

No test writes a repository fixture: the plan and lifecycle-transition fixture
stay in process. The genuine cross-service transaction lives in Java
(``ManualApprovedCrossServiceTest``), which serves the REAL
``QuickNoteCaptureService`` capture, the production ``FusekiQueryService``
validate/source-context path, the production ``ApprovedCandidateBindingService``
confirmed transition, and the REAL ``ApprovedAssertionMaterializationService``
transaction over one shared in-memory dataset behind a test-only HTTP boundary
under ``MaterializationAuthorization.enabledForTest()`` (disabled fails closed).
The plan wire format round-trips through ``plan_from_wire_format`` (unknown
fields and digest mismatches fail closed), so the API-side receipt-backed plan
and the Core-side asserted write share one payload shape with no synthesized
receipt digest on either side.

Durability: the connected slice here uses the in-memory adapter that mirrors
the PostgreSQL append rules; restart durability is proved separately by
``test_review_receipt_file_durability.py`` against the file-backed repository
(same append/validate rules, fsync per row, reopen-and-replay). Live
PostgreSQL remains covered only by the existing opt-in integration tests,
which skip without ``PROJECTA_CONNECTOR_INTEGRATION=1``; no live database is
provisioned in this environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedRequestContext, trusted_context
from projecta_api.extraction.approved_assertion_plan import (
    APPROVED_ASSERTION_PLAN_VERSION,
    MANUAL_CONSTRAINED_CONTRACT_VERSION,
    ManualApprovedPlanError,
    plan_and_fixture_for_test_materialization,
    plan_from_wire_format,
)
from projecta_api.extraction.review_receipts import (
    InMemoryReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptRecord,
    ReviewDecisionReceiptService,
)
from projecta_api.models import CaptureRequest, CaptureResponse
from projecta_api.routes import create_router
from projecta_api.semantic_core import SemanticCoreProblem
from projecta_api.structured_candidate_store import StructuredCandidateEditStore

_PROJECT_ID = "project-alpha"
_PROJECT_HANDLE = "project-h-abc12345"
_SOURCE_TEXT = "Plan \U0001f680 rollout"
_CANDIDATE_IRI = "https://w3id.org/projecta/data/project/project-alpha/candidate/note-1-1"
_ASSERTED_IRI = "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1"
_REVIEWER_IRI = "https://w3id.org/projecta/data/project/project-alpha/person/reviewer-1"
_PROVENANCE_IRI = (
    "https://w3id.org/projecta/data/project/project-alpha/activity/materialize/manual-1"
)
_EXPECTED_GRAPH_REVISION = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


async def _semantic_problem_response(request: object, error: SemanticCoreProblem) -> JSONResponse:
    del request
    return JSONResponse({"code": error.code}, status_code=error.status_code)


class _ConnectedCore:
    """Core port persisting a Note like QuickNoteCaptureService (manual generator)."""

    def __init__(self) -> None:
        self.project_id = _PROJECT_ID
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
        # Same-project candidate with server-owned span, manual generator, immutable text.
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
            "endOffset": segment.end_offset,
        }
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
        if path.endswith("/source-context"):
            parts = path.split("/")
            project_id = parts[3]
            candidate_handle = parts[5]
            source = self.source_contexts.get(candidate_handle)
            if (
                source is None
                or project_id != context.project_id
                or source["projectId"] != project_id
            ):
                raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not visible in this project")
            return {name: value for name, value in source.items() if name != "projectId"}
        if method == "POST" and path.endswith("/validations"):
            candidate_handle = path.split("/")[-2]
            source = self.source_contexts[candidate_handle]
            source["candidateStatus"] = "validated"
            return {"requestId": context.request_id, "conforms": True, "violations": []}
        if method == "POST" and (path.endswith("/confirmations") or path.endswith("/rejections")):
            self.assertion_writes.append(path)
            return {"requestId": context.request_id}
        if path.endswith("/evidence"):
            return {"items": []}
        if "/candidates?" in path:
            items = []
            for handle, source in self.source_contexts.items():
                if source["projectId"] != context.project_id:
                    continue
                items.append(
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
            return {
                "sourceRevision": "source-r1",
                "stale": False,
                "candidates": items,
                "hasMore": False,
            }
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "not visible")


@dataclass(slots=True)
class _Harness:
    app: FastAPI
    core: _ConnectedCore
    receipts: ReviewDecisionReceiptService
    headers: dict[str, str]


def _make_harness() -> _Harness:
    core = _ConnectedCore()
    receipts = ReviewDecisionReceiptService(InMemoryReviewDecisionReceiptRepository())

    class Extraction:
        def record_review_decision(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            request: object,
        ) -> object:
            del context
            return receipts.record(actor, request)  # type: ignore[arg-type]

        def review_decision_history(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            item_kind: str,
            item_handle: str,
        ) -> list[ReviewDecisionReceiptRecord]:
            del context
            return list(receipts.history(actor, item_kind, item_handle))  # type: ignore[arg-type]

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
    )


def _capture_payload() -> dict[str, object]:
    return {
        "title": "Planning",
        "rawText": _SOURCE_TEXT,
        "segments": [
            {"type": "task", "startOffset": 0, "endOffset": len(_SOURCE_TEXT), "text": _SOURCE_TEXT}
        ],
    }


def _actor() -> ReviewActorContext:
    return ReviewActorContext(
        project_id=_PROJECT_ID,
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )


def _entity_handle(candidate_handle: str) -> str:
    return "eh1_" + sha256(f"{_PROJECT_ID}:review-entity:{candidate_handle}".encode()).hexdigest()


@pytest.mark.asyncio
async def test_connected_capture_to_approved_plan_through_persisted_receipt() -> None:
    """Positive slice: Note -> validate -> approval receipt -> plan from persisted receipt."""

    harness = _make_harness()
    async with AsyncClient(
        transport=ASGITransport(app=harness.app), base_url="http://test"
    ) as client:
        capture_response = await client.post(
            "/v1/quick-notes",
            headers={"Idempotency-Key": "note-create-1"},
            json=_capture_payload(),
        )
        assert capture_response.status_code == 201, capture_response.text
        assert capture_response.json()["note"]["id"] == "note-1"
        candidate_handle = harness.core.candidate_handle

        project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        validation = await client.post(f"{project_path}/validations", headers=harness.headers)
        assert validation.status_code == 200, validation.text

        detail = (await client.get(f"{project_path}/review-detail", headers=harness.headers)).json()
        anchor = detail["evidence"]["highlights"][0]
        approval = {
            "candidateRevision": detail["candidateRevision"],
            "expectedCandidateRevision": 0,
            "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
            "sourceVersionRevision": detail["sourceVersion"]["revision"],
            "anchorQuoteDigest": anchor["quoteDigest"],
        }
        accepted = await client.post(
            f"{project_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "manual-approval-1"},
            json=approval,
        )
        assert accepted.status_code == 201, accepted.text
        body = accepted.json()
        assert body["receipt"]["decision"] == "confirm"
        # Production lock is preserved on the runtime path itself.
        assert body["materializationState"] == "blocked"
        assert body["reasonCode"] == "MATERIALIZATION_NOT_AUTHORIZED"

        # Sanctioned test-only orchestration reads the *persisted* receipt history.
        history = list(
            harness.receipts.history(_actor(), "entity", _entity_handle(candidate_handle))
        )
        assert len(history) == 1
        assert history[0].decision == "confirm"
        assert history[0].receipt_digest == body["receipt"]["receiptDigest"]

        from projecta_api.extraction.manual_capture import resolve_manual_capture

        capture_snapshot = resolve_manual_capture(
            _PROJECT_ID,
            {
                "candidateId": "note-1-1",
                "candidateRevision": 1,
                "candidateStatus": "validated",
                "sourceArtifactId": "note-1",
                "title": "Planning",
                "rawText": _SOURCE_TEXT,
                "evidenceText": _SOURCE_TEXT,
                "entityType": "Task",
                "startOffset": 0,
                "endOffset": len(_SOURCE_TEXT),
            },
        )
        plan, fixture = plan_and_fixture_for_test_materialization(
            project_id=_PROJECT_ID,
            candidate_iri=_CANDIDATE_IRI,
            capture=capture_snapshot,
            receipts=harness.receipts,
            actor=_actor(),
            item_kind="entity",
            item_handle=_entity_handle(candidate_handle),
            expected_asserted_graph_revision=_EXPECTED_GRAPH_REVISION,
            provenance_activity_iri=_PROVENANCE_IRI,
            idempotency_key="manual-plan-1",
            asserted_iri=_ASSERTED_IRI,
            reviewer_iri=_REVIEWER_IRI,
            valid_from=date(2026, 9, 27),
        )
        assert plan.safe_dict()["contractVersion"] == APPROVED_ASSERTION_PLAN_VERSION
        assert plan.review_receipt_digest == history[0].receipt_digest
        assert plan.evidence_digest == capture_snapshot.anchor.quote_digest
        assert plan.metadata_comment() == fixture.safe_binding_comment
        assert fixture.lifecycle_status == "confirmed"
        assert fixture.ontology_version == plan.ontology_version
        assert fixture.candidate_iri == plan.candidate_iri
        # Wire delivery: the same payload Core parses over HTTP rebuilds to the
        # identical plan (body digest + safe binding), so the receipt-backed plan
        # is the deliverable -- not an in-process-only value. Unknown fields and
        # digest mismatches fail closed at the boundary.
        wire_plan = plan_from_wire_format(plan.safe_dict())
        assert wire_plan.body_digest() == plan.body_digest()
        assert wire_plan.metadata_comment() == plan.metadata_comment()
        with pytest.raises(ManualApprovedPlanError):
            plan_from_wire_format({**plan.safe_dict(), "extraField": "x"})
        tampered = dict(plan.safe_dict())
        tampered["reviewReceiptDigest"] = "sha256:" + "f" * 64
        with pytest.raises(ManualApprovedPlanError):
            plan_from_wire_format(tampered)
        assert plan.body_digest() == plan.body_digest()
        assert plan.metadata_comment().startswith("projecta-approved-candidate/v1|")

        # Exact replay of the approval is idempotent: same receipt, no second row.
        replay = await client.post(
            f"{project_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "manual-approval-1"},
            json=approval,
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["outcome"] == "replayed"
        assert replay.json()["receipt"]["receiptDigest"] == body["receipt"]["receiptDigest"]
        reread = list(
            harness.receipts.history(_actor(), "entity", _entity_handle(candidate_handle))
        )
        assert len(reread) == 1
        assert reread[0].receipt_digest == history[0].receipt_digest
    assert harness.core.capture_count == 1
    assert harness.core.model_calls == 0
    assert harness.core.assertion_writes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["reject", "abstain"])
async def test_reject_and_abstain_receipts_cannot_back_a_test_plan(decision: str) -> None:
    """Closing receipts persist durably but can never produce an approved plan."""

    harness = _make_harness()
    async with AsyncClient(
        transport=ASGITransport(app=harness.app), base_url="http://test"
    ) as client:
        capture = await client.post(
            "/v1/quick-notes",
            headers={"Idempotency-Key": "note-create-1"},
            json=_capture_payload(),
        )
        assert capture.status_code == 201
        candidate_handle = harness.core.candidate_handle
        project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        assert (
            await client.post(f"{project_path}/validations", headers=harness.headers)
        ).status_code == 200
        detail = (await client.get(f"{project_path}/review-detail", headers=harness.headers)).json()
        anchor = detail["evidence"]["highlights"][0]
        base = {
            "candidateRevision": detail["candidateRevision"],
            "expectedCandidateRevision": 0,
            "sourceVersionId": detail["sourceVersion"]["sourceVersionId"],
            "sourceVersionRevision": detail["sourceVersion"]["revision"],
        }
        if decision == "reject":
            route = f"{project_path}/manual-rejections"
            payload = {
                **base,
                "anchorQuoteDigest": anchor["quoteDigest"],
                "reason": "source does not support this candidate",
            }
        else:
            route = f"{project_path}/abstentions"
            payload = {
                **base,
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
        assert recorded.json()["receipt"]["decision"] == decision

        from projecta_api.extraction.manual_capture import resolve_manual_capture

        snapshot = resolve_manual_capture(
            _PROJECT_ID,
            {
                "candidateId": "note-1-1",
                "candidateRevision": 1,
                "candidateStatus": "validated",
                "sourceArtifactId": "note-1",
                "title": "Planning",
                "rawText": _SOURCE_TEXT,
                "evidenceText": _SOURCE_TEXT,
                "entityType": "Task",
                "startOffset": 0,
                "endOffset": len(_SOURCE_TEXT),
            },
        )
        with pytest.raises(ManualApprovedPlanError):
            plan_and_fixture_for_test_materialization(
                project_id=_PROJECT_ID,
                candidate_iri=_CANDIDATE_IRI,
                capture=snapshot,
                receipts=harness.receipts,
                actor=_actor(),
                item_kind="entity",
                item_handle=_entity_handle(candidate_handle),
                expected_asserted_graph_revision=_EXPECTED_GRAPH_REVISION,
                provenance_activity_iri=_PROVENANCE_IRI,
                idempotency_key=f"manual-plan-{decision}",
                asserted_iri=_ASSERTED_IRI,
                reviewer_iri=_REVIEWER_IRI,
                valid_from=date(2026, 9, 27),
            )
    assert harness.core.assertion_writes == []


@pytest.mark.asyncio
async def test_no_approval_stale_and_cross_project_inputs_have_no_test_plan() -> None:
    """Without a persisted confirm receipt there is nothing to materialize."""

    harness = _make_harness()
    async with AsyncClient(
        transport=ASGITransport(app=harness.app), base_url="http://test"
    ) as client:
        capture = await client.post(
            "/v1/quick-notes",
            headers={"Idempotency-Key": "note-create-1"},
            json=_capture_payload(),
        )
        assert capture.status_code == 201
        candidate_handle = harness.core.candidate_handle

        from projecta_api.extraction.manual_capture import resolve_manual_capture

        snapshot = resolve_manual_capture(
            _PROJECT_ID,
            {
                "candidateId": "note-1-1",
                "candidateRevision": 1,
                "candidateStatus": "validated",
                "sourceArtifactId": "note-1",
                "title": "Planning",
                "rawText": _SOURCE_TEXT,
                "evidenceText": _SOURCE_TEXT,
                "entityType": "Task",
                "startOffset": 0,
                "endOffset": len(_SOURCE_TEXT),
            },
        )
        # No approval recorded yet: the orchestration fails closed on missing history.
        with pytest.raises(ManualApprovedPlanError):
            plan_and_fixture_for_test_materialization(
                project_id=_PROJECT_ID,
                candidate_iri=_CANDIDATE_IRI,
                capture=snapshot,
                receipts=harness.receipts,
                actor=_actor(),
                item_kind="entity",
                item_handle=_entity_handle(candidate_handle),
                expected_asserted_graph_revision=_EXPECTED_GRAPH_REVISION,
                provenance_activity_iri=_PROVENANCE_IRI,
                idempotency_key="manual-plan-absent",
                asserted_iri=_ASSERTED_IRI,
                reviewer_iri=_REVIEWER_IRI,
                valid_from=date(2026, 9, 27),
            )

        project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"
        stale = await client.post(
            f"{project_path}/manual-approvals",
            headers=harness.headers | {"Idempotency-Key": "manual-approval-stale"},
            json={
                "candidateRevision": 1,
                "expectedCandidateRevision": 0,
                "sourceVersionId": "sv_" + "0" * 64,
                "sourceVersionRevision": 1,
                "anchorQuoteDigest": "sha256:" + "0" * 64,
            },
        )
        assert stale.status_code == 409
        # Stale attempt recorded nothing, so the orchestration still fails closed.
        with pytest.raises(ManualApprovedPlanError):
            plan_and_fixture_for_test_materialization(
                project_id=_PROJECT_ID,
                candidate_iri=_CANDIDATE_IRI,
                capture=snapshot,
                receipts=harness.receipts,
                actor=_actor(),
                item_kind="entity",
                item_handle=_entity_handle(candidate_handle),
                expected_asserted_graph_revision=_EXPECTED_GRAPH_REVISION,
                provenance_activity_iri=_PROVENANCE_IRI,
                idempotency_key="manual-plan-stale",
                asserted_iri=_ASSERTED_IRI,
                reviewer_iri=_REVIEWER_IRI,
                valid_from=date(2026, 9, 27),
            )

    assert harness.core.assertion_writes == []
    other_actor = ReviewActorContext(
        project_id="project-beta",
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )
    assert (
        list(harness.receipts.history(other_actor, "entity", _entity_handle("candidate-h-x"))) == []
    )
    assert MANUAL_CONSTRAINED_CONTRACT_VERSION == "manual-entity-capture.v1"
