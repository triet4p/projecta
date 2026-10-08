"""S13-02 single-pipe e2e: real API receipt bytes into the real Java Core socket.

One OS process pipes the API's actual receipt-backed plan bytes into the SAME
Java Core instance that owns the captured candidate: Quick Note capture runs
through the real API route stack against a live Java ``SinglePipeCoreBoundary``
(real ``QuickNoteCaptureService`` row, no hand-seeded RDF), review/approval
persists a confirm receipt in live PostgreSQL (``s13-02-pg``), the versioned
plan is built from THAT persisted receipt, its serialized ``safe_dict`` bytes
are POSTed to the same Java boundary's ``/test/materialize`` probe, and the
production ``ApprovedCandidateBindingService`` (``enabledForTest``) plus the
real RM-63 materializer transact the asserted graph. Disabled-first fails
closed with zero asserted writes; replay is idempotent; no-approval, reject,
stale, and cross-project inputs cannot transact. Zero model calls.

Production stays locked: the API approval route still returns
``blocked``/``MATERIALIZATION_NOT_AUTHORIZED``, the Java production
composition never wires the materializer, and the Java subprocess serves only
test-only endpoints. Opt-in via ``PROJECTA_S13_SINGLE_PIPE=1`` plus the live
PostgreSQL env (host/port/name/user/password); otherwise the module skips.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from projecta_api.config import Settings
from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedRequestContext, trusted_context
from projecta_api.extraction.approved_assertion_plan import (
    MANUAL_CONSTRAINED_CONTRACT_VERSION,
    ManualApprovedPlanError,
    plan_and_fixture_for_test_materialization,
)
from projecta_api.extraction.review_receipts import (
    PostgresReviewDecisionReceiptRepository,
    ReviewActorContext,
    ReviewDecisionReceiptRecord,
    ReviewDecisionReceiptService,
)
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.routes import create_router
from projecta_api.semantic_core import HttpSemanticCoreClient, SemanticCoreProblem
from projecta_api.structured_candidate_store import StructuredCandidateEditStore

pytestmark = pytest.mark.local_contract

_PROJECT_ID = "project-alpha"
_PROJECT_HANDLE = "project-h-abc12345"
_SOURCE_TEXT = "Plan \U0001f680 rollout"
_ASSERTED_IRI = "https://w3id.org/projecta/data/project/project-alpha/requirement/req-manual-1"
_REVIEWER_IRI = "https://w3id.org/projecta/data/project/project-alpha/person/reviewer-1"
_PROVENANCE_IRI = (
    "https://w3id.org/projecta/data/project/project-alpha/activity/materialize/manual-1"
)
_VALID_FROM = date(2026, 9, 27)

_CORE_CLASS = "org.projecta.semanticcore.ManualApprovedCrossServiceTest$SinglePipeCoreBoundary"

_CORE_ENV = ("PROJECTA_S13_SINGLE_PIPE", "PROJECTA_CONNECTOR_INTEGRATION")
_DB_ENV = (
    "PROJECTA_CONNECTOR_DATABASE_HOST",
    "PROJECTA_CONNECTOR_DATABASE_PORT",
    "PROJECTA_CONNECTOR_DATABASE_NAME",
    "PROJECTA_CONNECTOR_DATABASE_USER",
    "PROJECTA_CONNECTOR_DATABASE_PASSWORD",
)


def _enabled() -> bool:
    return all(os.getenv(name) == "1" for name in _CORE_ENV) and all(
        os.getenv(name) for name in _DB_ENV
    )


def _core_root() -> Path:
    """Resolve the repository Java Core root only for enabled host runs."""

    return Path(__file__).resolve().parents[3] / "services" / "semantic-core"


async def _semantic_problem_response(request: object, error: SemanticCoreProblem) -> JSONResponse:
    del request
    return JSONResponse({"code": error.code}, status_code=error.status_code)


def _entity_handle(candidate_handle: str) -> str:
    return "eh1_" + sha256(f"{_PROJECT_ID}:review-entity:{candidate_handle}".encode()).hexdigest()


def _actor() -> ReviewActorContext:
    return ReviewActorContext(
        project_id=_PROJECT_ID,
        actor_id="reviewer-1",
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )
def _run_suffix() -> str:
    """Unique per-run suffix so the shared live DB never collides across runs."""

    return sha256(f"s13-single-pipe:{os.getpid()}:{time.monotonic_ns()}".encode()).hexdigest()[:12]



@contextmanager
def _java_boundary() -> Iterator[str]:
    """Launch the real Java SinglePipeCoreBoundary and yield its base URL."""
    core_root = _core_root()
    classpath_file = core_root / "target" / "s13-cp.txt"
    assert classpath_file.is_file(), "Java test classpath is not built (target/s13-cp.txt)"
    classpath = (
        f"target/test-classes;target/classes;{classpath_file.read_text(encoding='utf-8').strip()}"
    )
    process = subprocess.Popen(
        ["java", "-cp", classpath, _CORE_CLASS],
        cwd=str(core_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        assert process.stdout is not None
        port = 0
        deadline = time.monotonic() + 90.0
        buffered = ""
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    raise RuntimeError(f"Java boundary exited early: {buffered}")
                time.sleep(0.1)
                continue
            buffered += line
            match = re.search(r"S13_SINGLE_PIPE_PORT=(\d+)", line)
            if match:
                port = int(match.group(1))
                break
        assert port, f"Java boundary did not report a port: {buffered[-2000:]}"
        base = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                    break
            except OSError:
                time.sleep(0.1)
        # Readiness: the real candidate queue answers on the shared dataset.
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            try:
                response = httpx.get(
                    f"{base}/v1/projects/{_PROJECT_ID}/candidates?limit=1",
                    headers={
                        "X-Projecta-Project-Id": _PROJECT_ID,
                        "X-Projecta-Actor-Id": "reviewer-1",
                    },
                    timeout=3.0,
                )
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("Java boundary never became ready")
        yield base
    finally:
        process.terminate()
        try:
            process.wait(timeout=15.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15.0)


def _make_app(core: HttpSemanticCoreClient, receipts: ReviewDecisionReceiptService) -> FastAPI:
    class Extraction:
        def record_review_decision(
            self,
            context: TrustedRequestContext,
            actor: ReviewActorContext,
            request: object,
        ) -> ReviewDecisionReceiptRecord:
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
        project_id=_PROJECT_ID, actor_id="reviewer-1", request_id="req-1"
    )
    return app


def _capture_payload() -> dict[str, object]:
    return {
        "title": "Planning",
        "rawText": _SOURCE_TEXT,
        "segments": [
            {"type": "task", "startOffset": 0, "endOffset": len(_SOURCE_TEXT), "text": _SOURCE_TEXT}
        ],
    }


@pytest.mark.asyncio
async def test_single_pipe_api_receipt_into_same_java_core_transaction() -> None:
    """One pipe: API receipt bytes -> SAME Java candidate -> asserted graph."""
    if not _enabled():
        pytest.skip("single-pipe e2e needs PROJECTA_S13_SINGLE_PIPE=1 with live Postgres env")
    database = ConnectorDatabase(Settings())
    database.check_ready()
    try:
        receipts = ReviewDecisionReceiptService(PostgresReviewDecisionReceiptRepository(database))
        with _java_boundary() as core_base:
            run = _run_suffix()
            core = HttpSemanticCoreClient(core_base)
            app = _make_app(core, receipts)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Real Quick Note capture through the API into the Java-owned row.
                capture = await client.post(
                    "/v1/quick-notes",
                    headers={"Idempotency-Key": f"s13-single-pipe-note-{run}"},
                    json=_capture_payload(),
                )
                assert capture.status_code == 201, capture.text
                queue = await client.get(
                    f"/v1/projects/{_PROJECT_HANDLE}/candidates?status=pending-review&limit=100",
                    headers={"X-Projecta-Selection-Handle": _PROJECT_HANDLE},
                )
                assert queue.status_code == 200, queue.text
                rows = queue.json()["candidates"]
                assert len(rows) == 1
                candidate_handle = rows[0]["handle"]
                assert candidate_handle.startswith("candidate-h-")
                project_path = f"/v1/projects/{_PROJECT_HANDLE}/candidates/{candidate_handle}"

                # 2. Production promotion path on the SAME Java row.
                validation = await client.post(
                    f"{project_path}/validations",
                    headers={"X-Projecta-Selection-Handle": _PROJECT_HANDLE},
                )
                assert validation.status_code == 200, validation.text

                # 3. Real review + approval; receipt persists in live Postgres.
                detail = (
                    await client.get(
                        project_path + "/review-detail",
                        headers={"X-Projecta-Selection-Handle": _PROJECT_HANDLE},
                    )
                ).json()
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
                    headers={
                        "X-Projecta-Selection-Handle": _PROJECT_HANDLE,
                        "Idempotency-Key": f"s13-single-pipe-approval-{run}",
                    },
                    json=approval,
                )
                assert accepted.status_code == 201, accepted.text
                body = accepted.json()
                assert body["receipt"]["decision"] == "confirm"
                assert body["materializationState"] == "blocked"
                assert body["reasonCode"] == "MATERIALIZATION_NOT_AUTHORIZED"

                # Durable evidence: the SAME receipt is re-readable from Postgres.
                history = list(
                    receipts.history(_actor(), "entity", _entity_handle(candidate_handle))
                )
                assert len(history) == 1
                assert history[0].receipt_digest == body["receipt"]["receiptDigest"]

                # 4. Versioned plan built from THAT persisted receipt + live source context.
                async with httpx.AsyncClient(base_url=core_base, timeout=10.0) as java:
                    probe = await java.get(
                        f"/v1/projects/{_PROJECT_ID}/candidates/{candidate_handle}/source-context",
                        headers={
                            "X-Projecta-Project-Id": _PROJECT_ID,
                            "X-Projecta-Actor-Id": "reviewer-1",
                        },
                    )
                    assert probe.status_code == 200, probe.text
                    source_context = probe.json()
                    candidate_id = source_context["candidateId"]
                    candidate_iri = (
                        f"https://w3id.org/projecta/data/project/{_PROJECT_ID}"
                        f"/candidate/{candidate_id}"
                    )
                    revision = await java.get(
                        f"{core_base}/test/asserted-revision",
                        headers={
                            "X-Projecta-Project-Id": _PROJECT_ID,
                            "X-Projecta-Actor-Id": "reviewer-1",
                        },
                    )
                    assert revision.status_code == 200
                    from projecta_api.extraction.manual_capture import resolve_manual_capture

                    snapshot = resolve_manual_capture(_PROJECT_ID, source_context)
                    plan, _fixture = plan_and_fixture_for_test_materialization(
                        project_id=_PROJECT_ID,
                        candidate_iri=candidate_iri,
                        capture=snapshot,
                        receipts=receipts,
                        actor=_actor(),
                        item_kind="entity",
                        item_handle=_entity_handle(candidate_handle),
                        expected_asserted_graph_revision=revision.text,
                        provenance_activity_iri=_PROVENANCE_IRI,
                        idempotency_key=f"s13-single-pipe-plan-{run}",
                        asserted_iri=_ASSERTED_IRI,
                        reviewer_iri=_REVIEWER_IRI,
                        valid_from=_VALID_FROM,
                    )
                    assert plan.review_receipt_digest == history[0].receipt_digest
                    assert plan.evidence_digest == snapshot.anchor.quote_digest

                    # 5. SAME Java candidate: disabled-first fails closed, zero writes.
                    wire = plan.safe_dict()
                    blocked = await java.post(
                        f"{core_base}/test/materialize?authorization=disabled", json=wire
                    )
                    assert blocked.status_code == 423, blocked.text
                    size = await java.get(f"{core_base}/test/asserted-size")
                    assert size.text == "0"

                    # 6. Test-authorized transaction on the SAME bytes and SAME row.
                    transacted = await java.post(
                        f"{core_base}/test/materialize?authorization=test", json=wire
                    )
                    assert transacted.status_code == 200, transacted.text
                    result = transacted.json()
                    assert result["outcome"] == "accepted"
                    assert result["bodyDigest"] == plan.body_digest()
                    assert result["materializationRevision"].startswith("sha256:")
                    contains = await java.get(
                        f"{core_base}/test/asserted-contains?iri={_ASSERTED_IRI}"
                    )
                    assert contains.text == "true"

                    # 7. Exact replay of the SAME bytes is idempotent.
                    replay = await java.post(
                        f"{core_base}/test/materialize?authorization=test", json=wire
                    )
                    assert replay.status_code == 200, replay.text
                    assert replay.json()["outcome"] == "replayed"
                    assert (
                        replay.json()["materializationRevision"]
                        == result["materializationRevision"]
                    )

                    # 8. Fail-closed scope: approval/reject/stale/cross-project cannot transact.
                    legacy = await client.post(
                        f"{project_path}/confirmations",
                        headers={
                            "X-Projecta-Selection-Handle": _PROJECT_HANDLE,
                            "Idempotency-Key": f"s13-single-pipe-legacy-{run}",
                        },
                        json={
                            "assertion": {"type": "Requirement", "label": "x", "validFrom": "2026-09-27"},
                            "correctionRevision": 0,
                        },
                    )
                    assert legacy.status_code == 409, legacy.text
                    assert legacy.json()["code"] in (
                        "MATERIALIZATION_NOT_AUTHORIZED",
                        "MANUAL_CAPTURE_INVALID",
                    ), legacy.text
                    tampered = dict(wire)
                    tampered["reviewReceiptDigest"] = "sha256:" + "f" * 64
                    tampered["idempotencyKey"] = f"s13-single-pipe-tampered-{run}"
                    tampered_response = await java.post(
                        f"{core_base}/test/materialize?authorization=test", json=tampered
                    )
                    assert tampered_response.status_code in (422, 423)
                    cross_project = dict(wire)
                    cross_project["project"] = "project-beta"
                    cross_project["idempotencyKey"] = f"s13-single-pipe-cross-{run}"
                    cross_response = await java.post(
                        f"{core_base}/test/materialize?authorization=test", json=cross_project
                    )
                    assert cross_response.status_code in (422, 423)
                    with pytest.raises(ManualApprovedPlanError):
                        plan_and_fixture_for_test_materialization(
                            project_id="project-beta",
                            candidate_iri=candidate_iri,
                            capture=snapshot,
                            receipts=receipts,
                            actor=ReviewActorContext(
                                project_id="project-beta",
                                actor_id="reviewer-1",
                                capability="candidate.review",
                                authorization_revision="trusted-context.v1",
                            ),
                            item_kind="entity",
                            item_handle=_entity_handle(candidate_handle),
                            expected_asserted_graph_revision=revision.text,
                            provenance_activity_iri=_PROVENANCE_IRI,
                            idempotency_key=f"s13-single-pipe-cross-plan-{run}",
                            asserted_iri=_ASSERTED_IRI,
                            reviewer_iri=_REVIEWER_IRI,
                            valid_from=_VALID_FROM,
                        )
                assert MANUAL_CONSTRAINED_CONTRACT_VERSION == "manual-entity-capture.v1"
    finally:
        database.dispose()
