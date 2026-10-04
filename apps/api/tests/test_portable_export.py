from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Response

import projecta_api.portable_export as export_module
from projecta_api.extraction.correction_burden import (
    CorrectionBurdenRequest,
    CorrectionBurdenTelemetryService,
    InMemoryCorrectionBurdenRepository,
    _request_digest_from_event,
)
from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.structured_candidate_store import StructuredCandidateEditStore
from projecta_api.config import Settings
from projecta_api.context import TrustedActorContext, TrustedRequestContext
from projecta_api.evidence import EvidencePutRequest, LocalEvidenceStore
from projecta_api.structured_note import StructuredCandidateEditRequest, StructuredNoteDraft
from projecta_api.structured_note_store import (
    StructuredNoteDraftStore,
    structured_note_draft_fingerprint,
)
from projecta_api.export_fence import ExportWriteAttempted, ProjectWriteFence
from projecta_api.main import create_app
from projecta_api.portable_export import (
    PORTABLE_CONTRACT,
    PortableExportFailure,
    ProjectPortableExportService,
    _Payload,
    _canonical_json,
    _verify_archive,
    _write_archive,
    project_source_revision,
)
from projecta_api.project_workspace import catalog_revision, opaque_project_handle
from projecta_api.semantic_core import HttpSemanticCoreClient, SemanticCoreProblem


class ExportCore:
    async def project_catalog(
        self, context: TrustedActorContext, project_ids: list[str], limit: int = 100
    ) -> object:
        return {
            "catalogRevision": catalog_revision(tuple(sorted(project_ids))),
            "projects": [
                {
                    "projectId": project_id,
                    "name": project_id.title(),
                    "summary": f"{project_id.title()} summary",
                    "status": "active",
                    "counts": {
                        "requirements": 1,
                        "tasks": 0,
                        "questions": 0,
                        "risks": 0,
                        "notes": 1,
                        "candidates": 0,
                    },
                    "lastActivityAt": None,
                    "health": "fresh",
                    "freshnessState": "current",
                    "freshnessRevision": "projection-1",
                }
                for project_id in project_ids[:limit]
            ],
        }

    async def request(
        self,
        context: TrustedRequestContext,
        method: str,
        path: str,
        body: object | None = None,
        key: str | None = None,
    ) -> object:
        if path.endswith("/overview"):
            return {
                "project": {
                    "projectId": context.project_id,
                    "name": "Alpha Project",
                    "tenantId": None,
                    "createdAt": "2026-10-03T12:00:00Z",
                    "updatedAt": "2026-10-03T12:00:00Z",
                },
                "currentRequirements": [],
                "recentNotes": [],
                "reviewQueueCount": 0,
                "assertionCount": 0,
            }
        return {}

    async def readiness(self) -> bool:
        return True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("java_runtime", "supported"),
    [("21.0.12.1+1-LTS", True), ("21.0.12.1+1", False)],
)
async def test_semantic_export_enforces_exact_java_runtime_header(
    tmp_path, java_runtime: str, supported: bool
) -> None:
    headers = {
        "content-type": "application/trig",
        "x-projecta-java-runtime": java_runtime,
        "x-projecta-fuseki-version": "6.2.0",
        "x-projecta-semantic-core-javalin": "7.2.2",
        "x-projecta-semantic-core-jena": "6.2.0",
        "x-projecta-graph-triple-count": "0",
    }
    client = HttpSemanticCoreClient(
        "http://semantic-core",
        MockTransport(lambda request: Response(200, headers=headers, content=b"")),
    )
    target = tmp_path / "semantic.trig"
    context = TrustedRequestContext("alpha", "actor", "runtime-version-test")

    if supported:
        assert await client.stream_project_trig(context, target, 1024) == 0
        assert target.read_bytes() == b""
    else:
        with pytest.raises(SemanticCoreProblem) as failure:
            await client.stream_project_trig(context, target, 1024)
        assert failure.value.code == "EXPORT_UNSUPPORTED_VERSION"
        assert not target.exists()


@pytest.mark.parametrize(
    ("overview", "project_id"),
    [
        ({}, "alpha"),
        (
            {
                "project": {
                    "projectId": "beta",
                    "freshnessRevision": "catalog-r-" + "0" * 40,
                }
            },
            "alpha",
        ),
        (
            {"project": {"projectId": "alpha", "freshnessRevision": "projection-1"}},
            "alpha",
        ),
    ],
)
def test_source_revision_rejects_missing_mismatched_or_noncanonical_metadata(
    overview: object, project_id: str
) -> None:
    with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
        project_source_revision(overview, project_id)


@pytest.mark.parametrize("source_revision", [None, "projection-1", "catalog-r-" + "A" * 40])
def test_archive_verifier_rejects_pre_amendment_or_invalid_source_revision(
    tmp_path, source_revision: str | None
) -> None:
    source_path = tmp_path / "payload.txt"
    payload_bytes = b"project data"
    source_path.write_bytes(payload_bytes)
    payload = _Payload(
        path="payload/test.txt",
        role="test",
        media_type="text/plain",
        file_path=source_path,
        size_bytes=len(payload_bytes),
        sha256=hashlib.sha256(payload_bytes).hexdigest(),
    )
    manifest: dict[str, object] = {
        "portableContract": PORTABLE_CONTRACT,
        "exportId": "7cccb4d4-38a5-4c96-a5c4-c7d90ae5c57a",
        "exportedAt": "2026-10-03T12:00:00Z",
        "project": {"projectId": "alpha", "projectName": "Alpha", "tenantId": None},
        "producer": {},
        "evidenceReferences": [],
        "counts": {},
        "entries": [],
    }
    if source_revision is not None:
        manifest["sourceRevision"] = source_revision
    manifest_bytes = _canonical_json(manifest)
    archive_path = tmp_path / "proposal.projecta"
    payloads = (payload,)
    _write_archive(archive_path, manifest_bytes, payloads)

    with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
        _verify_archive(
            archive_path,
            manifest_bytes,
            payloads,
            len(manifest_bytes) + len(payload_bytes),
            "catalog-r-" + "0" * 40,
        )



@pytest.mark.asyncio
async def test_write_attempt_during_export_aborts_and_releases_fence() -> None:
    fence = ProjectWriteFence()

    with pytest.raises(ExportWriteAttempted):
        async with fence.export_epoch():
            assert await fence.enter_write() is False

    assert await fence.enter_write() is True
    await fence.exit_write()


def test_archive_writer_removes_partial_output_after_size_overage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload_bytes = b"bounded"
    source_path = tmp_path / "payload.txt"
    source_path.write_bytes(payload_bytes)
    payload = _Payload(
        path="payload/test.txt",
        role="test",
        media_type="text/plain",
        file_path=source_path,
        size_bytes=len(payload_bytes),
        sha256=hashlib.sha256(payload_bytes).hexdigest(),
    )
    archive_path = tmp_path / "oversized.partial"
    monkeypatch.setattr(export_module, "MAX_ARCHIVE_BYTES", 1)

    with pytest.raises(PortableExportFailure, match="EXPORT_TOO_LARGE"):
        _write_archive(archive_path, b"{}", (payload,))

    assert not archive_path.exists()


def test_archive_verifier_rejects_payload_digest_corruption(tmp_path) -> None:
    payload_bytes = b"authoritative payload"
    source_path = tmp_path / "payload.txt"
    source_path.write_bytes(payload_bytes)
    payload = _Payload(
        path="payload/test.txt",
        role="test",
        media_type="text/plain",
        file_path=source_path,
        size_bytes=len(payload_bytes),
        sha256=hashlib.sha256(payload_bytes).hexdigest(),
    )
    source_revision = "catalog-r-" + "0" * 40
    manifest_bytes = _canonical_json(
        {
            "portableContract": PORTABLE_CONTRACT,
            "exportId": "7cccb4d4-38a5-4c96-a5c4-c7d90ae5c57a",
            "exportedAt": "2026-10-03T12:00:00Z",
            "project": {"projectId": "alpha", "projectName": "Alpha", "tenantId": None},
            "sourceRevision": source_revision,
            "producer": {},
            "evidenceReferences": [],
            "counts": {},
            "entries": [payload.manifest_entry()],
        }
    )
    payloads = (payload,)
    expanded_limit = len(manifest_bytes) + len(payload_bytes)
    good_archive = tmp_path / "valid.projecta"
    _write_archive(good_archive, manifest_bytes, payloads)
    corrupt_archive = tmp_path / "corrupt.projecta"
    with (
        zipfile.ZipFile(good_archive, "r") as source,
        zipfile.ZipFile(corrupt_archive, "w") as target,
    ):
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == payload.path:
                content = b"x" * len(content)
            target.writestr(info, content)

    with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
        _verify_archive(
            corrupt_archive, manifest_bytes, payloads, expanded_limit, source_revision
        )

def test_archive_verifier_rejects_incomplete_payload_snapshot(tmp_path) -> None:
    payload_bytes = b"required project payload"
    source_path = tmp_path / "payload.txt"
    source_path.write_bytes(payload_bytes)
    payload = _Payload(
        path="payload/test.txt",
        role="test",
        media_type="text/plain",
        file_path=source_path,
        size_bytes=len(payload_bytes),
        sha256=hashlib.sha256(payload_bytes).hexdigest(),
    )
    source_revision = "catalog-r-" + "0" * 40
    manifest_bytes = _canonical_json(
        {
            "portableContract": PORTABLE_CONTRACT,
            "exportId": "7cccb4d4-38a5-4c96-a5c4-c7d90ae5c57a",
            "exportedAt": "2026-10-03T12:00:00Z",
            "project": {"projectId": "alpha", "projectName": "Alpha", "tenantId": None},
            "sourceRevision": source_revision,
            "producer": {},
            "evidenceReferences": [],
            "counts": {},
            "entries": [payload.manifest_entry()],
        }
    )
    payloads = (payload,)
    expanded_limit = len(manifest_bytes) + len(payload_bytes)
    complete_archive = tmp_path / "complete.projecta"
    _write_archive(complete_archive, manifest_bytes, payloads)
    incomplete_archive = tmp_path / "incomplete.projecta"
    with (
        zipfile.ZipFile(complete_archive, "r") as source,
        zipfile.ZipFile(incomplete_archive, "w") as target,
    ):
        for info in source.infolist():
            if info.filename != payload.path:
                target.writestr(info, source.read(info.filename))

    with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
        _verify_archive(
            incomplete_archive, manifest_bytes, payloads, expanded_limit, source_revision
        )


@pytest.mark.asyncio
async def test_evidence_collection_aborts_on_corrupted_source_object(tmp_path) -> None:
    evidence_root = tmp_path / "evidence"
    evidence = LocalEvidenceStore(evidence_root)
    content = b"evidence"

    async def chunks():
        yield content

    receipt = await evidence.put(
        EvidencePutRequest(
            project_scope="alpha",
            content_type="text/plain",
            declared_size=len(content),
            declared_sha256=hashlib.sha256(content).hexdigest(),
            source_reference="local-export-smoke",
        ),
        chunks(),
    )
    object_path = (
        evidence_root
        / "objects"
        / "alpha"
        / receipt.sha256[:2]
        / receipt.sha256
        / "content"
    )
    object_path.write_bytes(b"evidencX")
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    service = ProjectPortableExportService(
        database,
        None,
        evidence,
        HttpSemanticCoreClient("http://127.0.0.1"),
        native_runtime_lock_held=True,
    )
    try:
        with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
            await service._write_evidence_payloads(
                "alpha",
                tmp_path / "snapshot",
                frozenset({receipt.evidence_reference}),
            )
    finally:
        database.close()

@pytest.mark.asyncio
async def test_evidence_export_rejects_a_missing_referenced_object(tmp_path) -> None:
    evidence_root = tmp_path / "evidence"
    evidence = LocalEvidenceStore(evidence_root)
    content = b"evidence"

    async def chunks():
        yield content

    receipt = await evidence.put(
        EvidencePutRequest(
            project_scope="alpha",
            content_type="text/plain",
            declared_size=len(content),
            declared_sha256=hashlib.sha256(content).hexdigest(),
            source_reference="local-export-smoke",
        ),
        chunks(),
    )
    (
        evidence_root
        / "objects"
        / "alpha"
        / receipt.sha256[:2]
        / receipt.sha256
        / "content"
    ).unlink()
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    service = ProjectPortableExportService(
        database,
        None,
        evidence,
        HttpSemanticCoreClient("http://127.0.0.1"),
        native_runtime_lock_held=True,
    )
    try:
        with pytest.raises(PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"):
            await service._write_evidence_payloads(
                "alpha",
                tmp_path / "snapshot",
                frozenset({receipt.evidence_reference}),
            )
    finally:
        database.close()

@pytest.mark.parametrize(
    ("occurred_at", "expected"),
    [
        (
            datetime(2026, 10, 4, 7, tzinfo=timezone(timedelta(hours=7))),
            "2026-10-04T00:00:00Z",
        ),
        (
            datetime(2026, 10, 4, 7, 0, 0, 123400, tzinfo=timezone(timedelta(hours=7))),
            "2026-10-04T00:00:00.1234Z",
        ),
    ],
)
def test_portable_timestamp_uses_canonical_utc_format(
    occurred_at: datetime, expected: str
) -> None:
    assert export_module._format_timestamp(occurred_at) == expected

@pytest.mark.asyncio
async def test_receipt_export_iterates_core_rows_without_store_span_reference(tmp_path) -> None:
    project_id = "alpha"
    quote = "a manually captured source span"
    evidence_digest = "sha256:" + hashlib.sha256(quote.encode("utf-8")).hexdigest()
    request_digest = "sha256:" + "1" * 64
    occurred_at = datetime(2026, 10, 4, 7, tzinfo=timezone(timedelta(hours=7)))
    receipt_digest = export_module._receipt_digest(request_digest, occurred_at)
    assert receipt_digest == export_module._receipt_digest(
        request_digest, occurred_at.astimezone(UTC)
    )
    row = SimpleNamespace(
        receipt_id="rr1_" + request_digest.removeprefix("sha256:"),
        project_id=project_id,
        project_digest=export_module._digest_text(project_id),
        actor_digest="sha256:" + "2" * 64,
        authorization_digest="sha256:" + "3" * 64,
        item_kind="entity",
        item_handle_digest="sha256:" + "4" * 64,
        decision="reject",
        candidate_revision=1,
        source_version_digest="sha256:" + "5" * 64,
        source_version_revision=1,
        constrained_contract_version="manual-entity-capture.v1",
        evidence_digest=evidence_digest,
        previous_decision_digest=None,
        idempotency_digest="sha256:" + "6" * 64,
        request_digest=request_digest,
        sequence=1,
        occurred_at=occurred_at,
        receipt_digest=receipt_digest,
    )

    class Result:
        # Core Connection scalars() returns only the selected receipt_id column.
        def __iter__(self):
            return iter((row,))

        def scalars(self):
            return iter((row.receipt_id,))

    class Connection:
        def execute(self, statement):
            return Result()

    receipt_path = tmp_path / "review-receipts.jsonl"
    count, receipt_digests = export_module._read_and_write_receipts(
        Connection(), project_id, receipt_path, limit=1
    )
    assert count == 1
    assert receipt_digests == {receipt_digest}
    exported_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert exported_receipt["evidenceDigest"] == evidence_digest
    assert exported_receipt["occurredAt"] == "2026-10-04T00:00:00Z"
    assert exported_receipt["receiptDigest"] == receipt_digest
    evidence = LocalEvidenceStore(tmp_path / "evidence")
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    service = ProjectPortableExportService(
        database,
        None,
        evidence,
        HttpSemanticCoreClient("http://127.0.0.1"),
        native_runtime_lock_held=True,
    )
    try:
        references = await service._write_evidence_payloads(
            project_id, tmp_path / "snapshot", frozenset()
        )
        assert references == ()
    finally:
        database.close()


def test_portable_export_iterates_core_correction_rows(tmp_path) -> None:
    project_id = "alpha"
    request = CorrectionBurdenRequest.model_validate(
        {
            "projectId": project_id,
            "itemKind": "entity",
            "itemId": "entity-1",
            "assertionId": "assertion-1",
            "sourceVersionId": "sv_" + "1" * 64,
            "sourceVersionRevision": 1,
            "reviewReceiptDigest": "sha256:" + "8" * 64,
            "correctionCategory": "minor",
            "correctionDimensions": ["label"],
            "reviewOutcome": "edited",
            "semanticEditCount": 1,
            "reviewLatencyMs": 120,
            "materializationState": "not-materialized",
            "inferenceState": "not-materialized",
            "idempotencyKey": "portable-export-core-row",
        }
    )
    event = CorrectionBurdenTelemetryService(InMemoryCorrectionBurdenRepository()).record(
        request
    )
    row_values = event.model_dump()
    row_values["request_digest"] = _request_digest_from_event(project_id, event)
    row_values["project_id"] = project_id
    row = SimpleNamespace(**row_values)

    class Result:
        # Core Connection scalars() returns only the selected event_id column.
        def __iter__(self):
            return iter((row,))

        def scalars(self):
            return iter((row.event_id,))

    class Connection:
        def execute(self, statement):
            return Result()

    destination = tmp_path / "correction-burden-events.jsonl"
    count = export_module._write_correction_events(
        Connection(),
        project_id,
        destination,
        frozenset({event.review_receipt_digest}),
        limit=1,
    )

    assert count == 1
    exported_event = json.loads(destination.read_text(encoding="utf-8"))
    assert exported_event["eventId"] == event.event_id
    assert exported_event["reviewReceiptDigest"] == event.review_receipt_digest


async def test_portable_export_requires_confirmation() -> None:
    settings = Settings(
        _env_file=None,
        trusted_context_secret="secret",
        runtime_mode="experience",
        experience_actor_id="actor-1",
        experience_project_catalog="alpha",
        portable_export_lock_held=True,
    )
    app = create_app(settings=settings, semantic_client=ExportCore())  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        catalog = await client.get("/v1/projects")
        assert catalog.status_code == 200
        handle = opaque_project_handle("alpha")
        selected = await client.post(
            "/v1/projects/selection",
            json={"handle": handle, "catalogRevision": catalog.json()["catalogRevision"]},
        )
        assert selected.status_code == 200

        response = await client.post(
            f"/v1/projects/{handle}/exports",
            json={"confirmed": False},
        )
        assert response.status_code == 400


async def test_portable_export_unsupported_without_lock() -> None:
    settings = Settings(
        _env_file=None,
        trusted_context_secret="secret",
        runtime_mode="experience",
        experience_actor_id="actor-1",
        experience_project_catalog="alpha",
        portable_export_lock_held=False,
    )
    app = create_app(settings=settings, semantic_client=ExportCore())  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        catalog = await client.get("/v1/projects")
        assert catalog.status_code == 200
        handle = opaque_project_handle("alpha")
        selected = await client.post(
            "/v1/projects/selection",
            json={"handle": handle, "catalogRevision": catalog.json()["catalogRevision"]},
        )
        assert selected.status_code == 200

        response = await client.post(
            f"/v1/projects/{handle}/exports",
            json={"confirmed": True},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "EXPORT_UNSUPPORTED_RUNTIME"


@pytest.mark.asyncio
async def test_portable_export_hides_an_unselected_project() -> None:
    settings = Settings(
        _env_file=None,
        trusted_context_secret="secret",
        runtime_mode="experience",
        experience_actor_id="actor-1",
        experience_project_catalog="alpha",
        portable_export_lock_held=True,
    )
    app = create_app(settings=settings, semantic_client=ExportCore())  # type: ignore[arg-type]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        catalog = await client.get("/v1/projects")
        assert catalog.status_code == 200
        selected = await client.post(
            "/v1/projects/selection",
            json={
                "handle": opaque_project_handle("alpha"),
                "catalogRevision": catalog.json()["catalogRevision"],
            },
        )
        assert selected.status_code == 200

        response = await client.post(
            f"/v1/projects/{opaque_project_handle('beta')}/exports",
            json={"confirmed": True},
        )

    assert response.status_code == 404
    assert response.json()["code"] == "PROJECT_NOT_FOUND"


def test_portable_export_serializes_sqlite_rows(tmp_path) -> None:
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    draft_store = StructuredNoteDraftStore(database)
    candidate_store = StructuredCandidateEditStore(database)
    candidate_handle = "candidate-h-export-test"
    candidate_edit = StructuredCandidateEditRequest.model_validate(
        {"entityType": "Task", "expectedRevision": 1}
    )
    draft = StructuredNoteDraft.model_validate({"title": "SQLite export", "items": []})
    try:
        draft_store.create("alpha", "actor", "export-draft", draft)
        candidate_store.append(
            "alpha", candidate_handle, "actor", "request", candidate_edit
        )
        destination = tmp_path / "project-workflows.json"
        result = export_module._write_sqlite_workflows(
            database,
            "alpha",
            destination,
            {candidate_handle: "urn:projecta:candidate:smoke"},
        )

        assert result["record_counts"] == {
            "structuredNoteDrafts": 1,
            "candidateEdits": 1,
            "suggestionWorkflows": 0,
            "suggestionAttempts": 0,
            "authoringCostEvents": 0,
        }
        payload = json.loads(destination.read_text(encoding="utf-8"))
        assert payload["structuredNoteDrafts"][0]["draft"] == draft.model_dump(
            mode="json", by_alias=True
        )
        assert payload["candidateEdits"][0]["corrections"] == candidate_edit.model_dump(
            mode="json", by_alias=True
        )
    finally:
        database.close()

def test_portable_export_serializes_committed_sqlite_draft(tmp_path) -> None:
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    draft_store = StructuredNoteDraftStore(database)
    candidate_store = StructuredCandidateEditStore(database)
    draft = StructuredNoteDraft.model_validate(
        {
            "title": "Committed SQLite export",
            "items": [{"itemType": "task", "content": "Preserve committed drafts."}],
            "draftStatus": "ready",
        }
    )
    try:
        stored, replayed = draft_store.create(
            "alpha", "actor", "export-committed-draft", draft
        )
        assert replayed is False
        committed = draft_store.mark_committed(
            "alpha", stored.handle, stored.revision, "note-export-smoke"
        )
        assert committed.fingerprint == structured_note_draft_fingerprint(draft)

        destination = tmp_path / "committed-workflows.json"
        result = export_module._write_sqlite_workflows(
            database, "alpha", destination, {}
        )

        assert result["record_counts"] == {
            "structuredNoteDrafts": 1,
            "candidateEdits": 0,
            "suggestionWorkflows": 0,
            "suggestionAttempts": 0,
            "authoringCostEvents": 0,
        }
        exported = json.loads(destination.read_text(encoding="utf-8"))[
            "structuredNoteDrafts"
        ][0]
        assert exported["draft"] == committed.draft.model_dump(
            mode="json", by_alias=True
        )
        committed_payload = json.dumps(
            committed.draft.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            sort_keys=True,
        )
        assert exported["payloadDigest"] == hashlib.sha256(
            committed_payload.encode("utf-8")
        ).hexdigest()
        assert exported["payloadDigest"] != committed.fingerprint
        assert exported["committedNoteId"] == "note-export-smoke"
    finally:
        database.close()


def test_portable_export_rejects_tampered_committed_sqlite_draft(tmp_path) -> None:
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    draft_store = StructuredNoteDraftStore(database)
    candidate_store = StructuredCandidateEditStore(database)
    draft = StructuredNoteDraft.model_validate(
        {
            "title": "Committed SQLite export",
            "items": [{"itemType": "task", "content": "Preserve committed drafts."}],
            "draftStatus": "ready",
        }
    )
    try:
        stored, _ = draft_store.create(
            "alpha", "actor", "export-tampered-committed-draft", draft
        )
        committed = draft_store.mark_committed(
            "alpha", stored.handle, stored.revision, "note-export-smoke"
        )
        tampered_payload = committed.draft.model_dump(mode="json", by_alias=True)
        tampered_payload["title"] = "Tampered committed draft"
        with database.transaction() as connection:
            connection.execute(
                "UPDATE structured_note_drafts SET payload = ? "
                "WHERE project_id = ? AND handle = ?",
                (
                    json.dumps(
                        tampered_payload, ensure_ascii=False, sort_keys=True
                    ),
                    "alpha",
                    committed.handle,
                ),
            )

        with pytest.raises(
            PortableExportFailure, match="EXPORT_INTEGRITY_FAILED"
        ):
            export_module._write_sqlite_workflows(
                database, "alpha", tmp_path / "tampered-workflows.json", {}
            )
    finally:
        database.close()

def test_portable_export_serializes_empty_connector_state_as_json(tmp_path) -> None:
    class EmptyResult:
        def all(self) -> list[object]:
            return []

        def first(self) -> None:
            return None

        def mappings(self) -> list[object]:
            return []

    class EmptyConnection:
        def execute(self, *_args: object, **_kwargs: object) -> EmptyResult:
            return EmptyResult()

    destination = tmp_path / "connectors.json"
    counts, inbox_references = export_module._write_connector_json(
        EmptyConnection(), "alpha", destination, limit=10
    )

    assert counts == {
        "installations": 0,
        "inbox": 0,
        "runs": 0,
        "attempts": 0,
        "cursors": 0,
        "deadLetters": 0,
        "auditEvents": 0,
    }
    assert inbox_references == frozenset()
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "schemaVersion": 1,
        "installations": [],
        "inbox": [],
        "runs": [],
        "attempts": [],
        "cursors": [],
        "deadLetters": [],
        "auditEvents": [],
    }
