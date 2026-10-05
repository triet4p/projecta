"""HTTP routes for typed capture, review, and finite read operations."""

import shutil
import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Literal, Protocol, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from projecta_api.connectors.public_api import ConnectorRuntime, add_connector_routes
from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.connection import ProviderConnectionChecker
from projecta_api.configuration.errors import ConfigurationProblem
from projecta_api.configuration.models import (
    LLMProfileRemove,
    LLMProfileWrite,
)
from projecta_api.configuration.ports import RuntimeConfigurationProvider
from projecta_api.configuration.service import LLMConfigurationService
from projecta_api.export_fence import ExportAlreadyRunning, ExportWriteAttempted, ProjectWriteFence
from projecta_api.portable_export import (
    ExportArtifact,
    PortableExportFailure,
    ProjectPortableExportService,
    project_source_revision,
)
from projecta_api.portable_import import PortableImportFailure, ProjectPortableImportService
from projecta_api.context import (
    TrustedActorContext,
    TrustedRequestContext,
    trusted_actor_context,
    trusted_context,
)
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.constrained_relation import allowed_relation_predicates
from projecta_api.extraction.controlled_relations import (
    ControlledRelationDecisionRequest,
    ControlledRelationEndpoint,
    ControlledRelationRequest,
    RelationDirection,
    RelationSuggestionMode,
    RelationSuggestionContext,
    RelationSuggestionOption,
    RelationSuggestionTarget,
    RelationSuggestionTargetsResponse,
    build_relation_suggestion_context,
    relation_workflow_item_handle,
)
from projecta_api.extraction.manual_capture import (
    ManualCaptureContextError,
    VerifiedManualCapture,
    resolve_manual_capture,
)
from projecta_api.extraction.authoring_telemetry import (
    AuthoringCostMetrics,
    CorrectionDimension,
)
from projecta_api.extraction.local_suggestion_store import LocalSuggestionStoreConflict
from projecta_api.extraction.local_suggestions import (
    MAX_LINK_TARGETS,
    LocalSuggestionDecisionRequest,
    LocalSuggestionError,
    LocalSuggestionKey,
    LocalSuggestionLinkOption,
    LocalSuggestionProposal,
    LocalSuggestionRequest,
    LocalSuggestionResponse,
    LocalSuggestionService,
    LocalSuggestionSubject,
    LocalSuggestionTarget,
)
from projecta_api.extraction.review_receipts import (
    ReviewActorContext,
    ReviewDecisionReceiptRecord,
    ReviewDecisionRequest,
    ReviewReceiptConflict,
    ReviewReceiptStaleError,
)
from projecta_api.graph_projection import (
    NODE_TYPES,
    RELATION_TYPES,
    CandidateQueueResponse,
    GraphEvidenceResponse,
    GraphLifecycleResponse,
    GraphNodeDetail,
    GraphProjectionResponse,
    KnowledgeCollectionResponse,
    ReviewWorkbenchDetailResponse,
    finite_types,
    mapping,
    opaque_or_hashed,
    opaque_navigation_handle,
    project_candidate_queue,
    project_graph_page,
    project_knowledge_collection,
    project_link_response,
    project_node_detail,
    project_review_detail,
    require_opaque_handle,
    required,
    required_list,
)
from projecta_api.identity.policy import require_capability
from projecta_api.models import (
    CaptureRequest,
    CaptureResponse,
    ConfirmationRequest,
    ExtractionRequest,
    RejectionRequest,
    TypedSegment,
)
from projecta_api.operational.errors import IdempotencyConflict, RevisionConflict
from projecta_api.project_workspace import (
    ProjectCatalogItem,
    ProjectCatalogResponse,
    ProjectOverviewResponse,
    ProjectReadResponse,
    ProjectSelectionRequest,
    ProjectSelectionResponse,
    configured_project_ids,
    opaque_project_handle,
    selection_revision,
)
from projecta_api.projections import (
    project_candidate_history,
    project_current_knowledge,
    project_evidence,
)
from projecta_api.retrieval.service import RetrievalService
from projecta_api.semantic_core import SemanticCoreClient, SemanticCoreProblem
from projecta_api.structured_candidate_store import CandidateEditConflict, StoredCandidateEdit
from projecta_api.structured_note import (
    CandidateEditOption,
    CandidateEditOptionsResponse,
    NoteItemType,
    StructuredCandidateEditRequest,
    StructuredNoteDetailResponse,
    StructuredNoteDraft,
    StructuredNoteDraftResponse,
    StructuredNoteImportRequest,
    StructuredNoteImportResponse,
    StructuredNoteItemDraft,
    StructuredNoteItemProjection,
    StructuredNoteListItem,
    StructuredNoteListResponse,
    canonicalize_structured_note,
)
from projecta_api.structured_note_store import (
    StoredStructuredNoteDraft,
    StructuredNoteDraftConflict,
    StructuredNoteDraftNotFound,
    StructuredNoteDraftStore,
    StructuredNoteIdempotencyConflict,
)

Context = Annotated[TrustedRequestContext, Depends(trusted_context)]
ActorContext = Annotated[TrustedActorContext, Depends(trusted_actor_context)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


class ProjectContextQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=100)


class ConnectionCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_seconds: float = Field(default=10.0, gt=0, le=15, alias="timeoutSeconds")


class PortableExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: Literal[True] = Field(alias="confirmed")

class PortableImportApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool

class ReviewAbstainRequest(BaseModel):
    """Trusted-boundary input for an explicit, receipt-backed abstention."""

    model_config = ConfigDict(extra="forbid")

    candidate_revision: int = Field(alias="candidateRevision", ge=1)
    expected_candidate_revision: int = Field(alias="expectedCandidateRevision", ge=0)
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=1)
    constrained_contract_version: str = Field(
        alias="constrainedContractVersion", min_length=1, max_length=64
    )
    evidence_digest: str | None = Field(
        default=None, alias="evidenceDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    previous_decision_digest: str | None = Field(
        default=None, alias="previousDecisionDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )


class ReviewAbstainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["review-receipt.v1"] = Field(alias="contractVersion")
    request_id: str = Field(alias="requestId")
    decision: Literal["abstain"]
    outcome: Literal["accepted", "replayed"]
    receipt: ReviewDecisionReceiptRecord
class ManualCaptureApprovalRequest(BaseModel):
    """Optimistic input for a human approval of a verified manual Note item."""

    model_config = ConfigDict(extra="forbid")

    candidate_revision: int = Field(alias="candidateRevision", ge=1)
    expected_candidate_revision: int = Field(alias="expectedCandidateRevision", ge=0)
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=1)
    anchor_quote_digest: str = Field(
        alias="anchorQuoteDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )


class ManualCaptureApprovalResponse(BaseModel):
    """Recorded approval receipt with the locked materialization result made explicit."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["manual-capture-approval.v1"] = Field(
        alias="contractVersion"
    )
    request_id: str = Field(alias="requestId")
    outcome: Literal["accepted", "replayed"]
    receipt: ReviewDecisionReceiptRecord
    materialization_state: Literal["blocked"] = Field(alias="materializationState")
    reason_code: Literal["MATERIALIZATION_NOT_AUTHORIZED"] = Field(alias="reasonCode")


class ManualCaptureRejectionRequest(ManualCaptureApprovalRequest):
    """Optimistic rejection input bound to the current manual Note anchor."""

    reason: str = Field(min_length=1, max_length=4096)


class ManualCaptureRejectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["manual-capture-decision.v1"] = Field(
        alias="contractVersion"
    )
    request_id: str = Field(alias="requestId")
    decision: Literal["rejected"]
    outcome: Literal["accepted", "replayed"]
    receipt: ReviewDecisionReceiptRecord







class ExtractionService(Protocol):
    async def extract(
        self, context: TrustedRequestContext, key: str, request: ExtractionRequest
    ) -> object: ...

    async def propose(
        self, context: TrustedRequestContext, request: ExtractionRequest
    ) -> ExtractionResponse: ...

    def record_review_decision(
        self, context: TrustedRequestContext, actor: ReviewActorContext, request: ReviewDecisionRequest
    ) -> ReviewDecisionReceiptRecord: ...

    def review_decision_history(
        self,
        context: TrustedRequestContext,
        actor: ReviewActorContext,
        item_kind: Literal["entity", "relation"],
        item_handle: str,
    ) -> Sequence[ReviewDecisionReceiptRecord]: ...


def create_router(
    client: SemanticCoreClient,
    extraction: ExtractionService | None = None,
    retrieval: RetrievalService | None = None,
    configuration_service: LLMConfigurationService | None = None,
    runtime_configuration: RuntimeConfigurationProvider | None = None,
    connection_checker: ProviderConnectionChecker | None = None,
    configuration_audit: ConfigurationAudit | None = None,
    connector_runtime: ConnectorRuntime | None = None,
    local_suggestions: LocalSuggestionService | None = None,
    portable_export: ProjectPortableExportService | None = None,
    portable_import: ProjectPortableImportService | None = None,
) -> APIRouter:
    """Create routes bound to one finite Semantic Core client."""
    router = APIRouter()

    @router.get("/v1/projects", response_model=ProjectCatalogResponse)
    async def list_projects(
        actor: ActorContext,
        request: Request,
        response: Response,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> ProjectCatalogResponse:
        result, _ = await _read_project_catalog(client, actor, _catalog_ids(request), limit)
        response.headers["X-Request-Id"] = actor.request_id
        return result

    @router.get("/v1/projects/{handle}", response_model=ProjectReadResponse)
    async def read_project(
        handle: str, actor: ActorContext, request: Request, response: Response
    ) -> ProjectReadResponse:
        result, internal = await _read_project_catalog(client, actor, _catalog_ids(request), 100)
        for item, _raw in zip(result.projects, internal, strict=True):
            if item.handle == handle:
                response.headers["X-Request-Id"] = actor.request_id
                return ProjectReadResponse(requestId=actor.request_id, project=item)
        raise _project_not_found()

    @router.post("/v1/projects/selection", response_model=ProjectSelectionResponse)
    async def select_project(
        payload: ProjectSelectionRequest,
        actor: ActorContext,
        request: Request,
        response: Response,
    ) -> ProjectSelectionResponse:
        repository = request.app.state.project_selection_repository
        repository.clear(actor.actor_id)
        result, internal = await _read_project_catalog(client, actor, _catalog_ids(request), 100)
        if payload.catalog_revision != result.catalog_revision:
            raise SemanticCoreProblem(
                409, "PROJECT_SELECTION_STALE", "The project catalog has changed"
            )
        for item, raw in zip(result.projects, internal, strict=True):
            if item.handle == payload.handle:
                project_id = str(raw["projectId"])
                selected = repository.replace(
                    actor.actor_id, item.handle, project_id, result.catalog_revision
                )
                response.headers["X-Request-Id"] = actor.request_id
                return ProjectSelectionResponse(
                    requestId=actor.request_id,
                    selectionRevision=selection_revision(
                        selected.handle, selected.catalog_revision
                    ),
                    project=item,
                )
        raise _project_not_found()

    @router.get("/v1/projects/{handle}/overview", response_model=ProjectOverviewResponse)
    async def project_overview(
        handle: str, context: Context, request: Request, response: Response
    ) -> ProjectOverviewResponse:
        selected_handle = request.headers.get("X-Projecta-Selection-Handle")
        if selected_handle != handle:
            raise _project_not_found()
        raw = await client.request(context, "GET", f"/v1/projects/{context.project_id}/overview")
        mapped = _map_project_overview(context.request_id, raw, handle)
        mapped["portableExportEnabled"] = bool(portable_export and portable_export.enabled())
        response.headers["X-Request-Id"] = context.request_id
        return ProjectOverviewResponse.model_validate(mapped)

    @router.post(
        "/v1/projects/{handle}/exports",
        response_class=FileResponse,
        responses={200: {"content": {"application/zip": {}}}},
    )
    async def export_project(
        handle: str,
        payload: PortableExportRequest,
        context: Context,
        request: Request,
        response: Response,
    ) -> FileResponse:
        _require_selected_project_handle(request, handle)
        if payload.confirmed is not True:
            raise PortableExportFailure("EXPORT_CONFIRMATION_REQUIRED")
        if portable_export is None or not portable_export.enabled():
            raise PortableExportFailure("EXPORT_UNSUPPORTED_RUNTIME", status_code=503)
        fence = cast(ProjectWriteFence, request.app.state.project_write_fence)
        artifact: ExportArtifact | None = None
        try:
            async with fence.export_epoch():
                raw = await client.request(
                    context, "GET", f"/v1/projects/{context.project_id}/overview"
                )
                project = mapping(required(mapping(raw), "project"))
                project_name = _required_string(project, "name")
                source_revision = project_source_revision(raw, context.project_id)
                artifact = await portable_export.create(
                    context,
                    project_name,
                    source_revision,
                    request.app.state.portable_export_root,
                )
                await fence.ensure_no_write_attempts()
        except (ExportAlreadyRunning, ExportWriteAttempted) as error:
            if artifact is not None:
                shutil.rmtree(artifact.work_directory, ignore_errors=True)
            raise PortableExportFailure("EXPORT_BUSY") from error
        except BaseException:
            if artifact is not None:
                shutil.rmtree(artifact.work_directory, ignore_errors=True)
            raise
        if artifact is None:
            raise PortableExportFailure("EXPORT_FAILED", status_code=503)
        response.headers["X-Request-Id"] = context.request_id
        response.headers["X-Projecta-Export-SHA256"] = artifact.sha256
        response.headers["X-Projecta-Export-Size-Bytes"] = str(artifact.size_bytes)
        response.headers["Cache-Control"] = "no-store"
        return FileResponse(
            artifact.path,
            media_type="application/zip",
            filename=artifact.filename,
            headers=response.headers,
            background=BackgroundTask(
                shutil.rmtree, artifact.work_directory, ignore_errors=True
            ),
        )

    @router.post("/v1/imports/previews")
    async def preview_portable_import(
        request: Request, actor: ActorContext, response: Response
    ) -> dict[str, object]:
        if portable_import is None or not portable_import.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        preview = await portable_import.create_preview(actor, request.stream())
        response.headers["X-Request-Id"] = actor.request_id
        response.headers["Cache-Control"] = "no-store"
        return {"requestId": actor.request_id, **preview.response()}

    @router.delete("/v1/imports/previews/{token}")
    async def cancel_portable_import(token: str, actor: ActorContext) -> dict[str, str]:
        if portable_import is None or not portable_import.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        await portable_import.cancel_preview(actor, token)
        return {"requestId": actor.request_id}

    @router.post("/v1/imports/previews/{token}/apply")
    async def apply_portable_import(
        token: str,
        payload: PortableImportApplyRequest,
        actor: ActorContext,
        request: Request,
        response: Response,
    ) -> dict[str, object]:
        if portable_import is None or not portable_import.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        fence = cast(ProjectWriteFence, request.app.state.project_write_fence)
        try:
            async with fence.maintenance_epoch():
                try:
                    result = await portable_import.apply(actor, token, payload.confirmed)
                    if result.get("restartRequired") is True:
                        await fence.require_recovery()
                except PortableImportFailure as error:
                    if error.code in {"IMPORT_RECOVERY_PENDING", "IMPORT_RECOVERY_REQUIRED"}:
                        await fence.require_recovery()
                    raise
        except ExportAlreadyRunning as error:
            raise PortableImportFailure("IMPORT_BUSY") from error
        response.headers["X-Request-Id"] = actor.request_id
        response.headers["Cache-Control"] = "no-store"
        return {"requestId": actor.request_id, **result}

    @router.get("/v1/imports/{token}")
    async def portable_import_result(
        token: str,
        actor: ActorContext,
        response: Response,
    ) -> dict[str, object]:
        if portable_import is None or not portable_import.enabled():
            raise PortableImportFailure("IMPORT_UNSUPPORTED_RUNTIME", status_code=503)
        result = await portable_import.result(actor, token)
        response.headers["X-Request-Id"] = actor.request_id
        response.headers["Cache-Control"] = "no-store"
        return {"requestId": actor.request_id, **result}

    @router.post(
        "/v1/projects/{handle}/notes/drafts",
        response_model=StructuredNoteDraftResponse,
        status_code=201,
    )
    async def create_note_draft(
        handle: str,
        payload: StructuredNoteDraft,
        context: Context,
        key: Key,
        request: Request,
        response: Response,
    ) -> StructuredNoteDraftResponse:
        _require_selected_project_handle(request, handle)
        store = _note_draft_store(request)
        try:
            stored, replayed = store.create(context.project_id, context.actor_id, key, payload)
        except StructuredNoteIdempotencyConflict as error:
            raise SemanticCoreProblem(
                409, "IDEMPOTENCY_KEY_REUSED", "The idempotency key belongs to a different draft"
            ) from error
        response.status_code = 200 if replayed else 201
        response.headers["X-Request-Id"] = context.request_id
        return _draft_response(context.request_id, stored, replayed)

    @router.get(
        "/v1/projects/{handle}/notes/drafts/{draft_handle}",
        response_model=StructuredNoteDraftResponse,
    )
    async def read_note_draft(
        handle: str,
        draft_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> StructuredNoteDraftResponse:
        _require_selected_project_handle(request, handle)
        _validate_handle(draft_handle, ("draft",))
        try:
            stored = _note_draft_store(request).get(context.project_id, draft_handle)
        except StructuredNoteDraftNotFound as error:
            raise SemanticCoreProblem(
                404, "RESOURCE_NOT_FOUND", "The draft is not visible in this project"
            ) from error
        response.headers["X-Request-Id"] = context.request_id
        return _draft_response(context.request_id, stored, False)

    @router.put(
        "/v1/projects/{handle}/notes/drafts/{draft_handle}",
        response_model=StructuredNoteDraftResponse,
    )
    async def update_note_draft(
        handle: str,
        draft_handle: str,
        payload: StructuredNoteDraft,
        context: Context,
        request: Request,
        response: Response,
        if_match: Annotated[int | None, Header(alias="If-Match", ge=1)] = None,
    ) -> StructuredNoteDraftResponse:
        _require_selected_project_handle(request, handle)
        _validate_handle(draft_handle, ("draft",))
        if if_match is None:
            raise SemanticCoreProblem(409, "NOTE_DRAFT_CONFLICT", "If-Match revision is required")
        try:
            stored = _note_draft_store(request).update(
                context.project_id, draft_handle, if_match, payload
            )
        except StructuredNoteDraftNotFound as error:
            raise SemanticCoreProblem(
                404, "RESOURCE_NOT_FOUND", "The draft is not visible in this project"
            ) from error
        except StructuredNoteDraftConflict as error:
            raise SemanticCoreProblem(
                409, "NOTE_DRAFT_CONFLICT", "The draft revision is stale"
            ) from error
        response.headers["X-Request-Id"] = context.request_id
        return _draft_response(context.request_id, stored, False)

    @router.post(
        "/v1/projects/{handle}/notes/drafts/{draft_handle}/commit",
        response_model=StructuredNoteDraftResponse,
    )
    async def commit_note_draft(
        handle: str,
        draft_handle: str,
        context: Context,
        key: Key,
        request: Request,
        response: Response,
    ) -> StructuredNoteDraftResponse:
        _require_selected_project_handle(request, handle)
        _validate_handle(draft_handle, ("draft",))
        store = _note_draft_store(request)
        try:
            stored = store.get(context.project_id, draft_handle)
        except StructuredNoteDraftNotFound as error:
            raise SemanticCoreProblem(
                404, "RESOURCE_NOT_FOUND", "The draft is not visible in this project"
            ) from error
        if stored.committed_note_id is not None:
            response.status_code = 200
            response.headers["X-Request-Id"] = context.request_id
            return _draft_response(context.request_id, stored, True)
        canonical = canonicalize_structured_note(stored.draft)
        if not canonical.items:
            raise SemanticCoreProblem(
                422, "INVALID_REQUEST", "A committed Note must contain an item"
            )
        capture = CaptureRequest(
            title=canonical.title,
            rawText=canonical.raw_text,
            segments=[
                TypedSegment(
                    type=item.item_type,
                    startOffset=item.start_offset,
                    endOffset=item.end_offset,
                    text=item.content,
                )
                for item in canonical.items
            ],
        )
        result = await client.capture(context, key, capture)
        try:
            committed = store.mark_committed(
                context.project_id, draft_handle, stored.revision, result.note.id
            )
        except StructuredNoteDraftConflict as error:
            raise SemanticCoreProblem(
                409, "NOTE_DRAFT_CONFLICT", "The draft changed during commit"
            ) from error
        response.status_code = 200 if result.replayed else 201
        response.headers["X-Request-Id"] = context.request_id
        return _draft_response(context.request_id, committed, result.replayed)

    @router.get(
        "/v1/projects/{handle}/notes",
        response_model=StructuredNoteListResponse,
    )
    async def list_structured_notes(
        handle: str,
        context: Context,
        request: Request,
        response: Response,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> StructuredNoteListResponse:
        _require_selected_project_handle(request, handle)
        drafts = [
            _draft_response(context.request_id, draft, False)
            for draft in _note_draft_store(request).list(context.project_id, limit)
        ]
        raw = await client.request(
            context,
            "GET",
            _core_query_path(f"/v1/projects/{context.project_id}/notes", {"limit": limit}),
        )
        committed = _map_note_list(raw)
        response.headers["X-Request-Id"] = context.request_id
        return StructuredNoteListResponse(
            requestId=context.request_id, drafts=drafts, committed=committed
        )

    @router.get(
        "/v1/projects/{handle}/notes/{note_handle}", response_model=StructuredNoteDetailResponse
    )
    async def read_structured_note(
        handle: str,
        note_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> object:
        _require_selected_project_handle(request, handle)
        _validate_handle(note_handle, ("note",))
        raw = await client.request(
            context, "GET", f"/v1/projects/{context.project_id}/notes/{note_handle}"
        )
        result = _map_note_detail(raw, context.request_id)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post(
        "/v1/projects/{handle}/notes/import",
        response_model=StructuredNoteImportResponse,
    )
    async def import_note_text(
        handle: str,
        payload: StructuredNoteImportRequest,
        context: Context,
        request: Request,
        response: Response,
    ) -> StructuredNoteImportResponse:
        _require_selected_project_handle(request, handle)
        extracted = await _require_dependency(extraction, "extraction").propose(
            context, ExtractionRequest(rawText=payload.raw_text)
        )
        if extracted.abstention_reason is not None:
            result = StructuredNoteImportResponse(
                requestId=context.request_id,
                status="abstained",
                title=payload.title,
                proposals=[],
                abstentionReason=extracted.abstention_reason,
            )
        else:
            if extracted.relations or extracted.links:
                raise SemanticCoreProblem(
                    422,
                    "IMPORT_PROPOSAL_UNREPRESENTABLE",
                    "The extraction contains relationships that the Note composer cannot represent",
                )
            proposals = _note_item_proposals(extracted)
            if not proposals:
                raise SemanticCoreProblem(
                    422,
                    "EXTRACTION_EMPTY",
                    "The extraction returned neither proposals nor an abstention reason",
                )
            result = StructuredNoteImportResponse(
                requestId=context.request_id,
                status="proposed",
                title=payload.title,
                proposals=proposals,
            )
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/projects/{handle}/candidates/{candidate_handle}/edits")
    async def edit_structured_candidate(
        handle: str,
        candidate_handle: str,
        payload: StructuredCandidateEditRequest,
        context: Context,
        request: Request,
        response: Response,
    ) -> object:
        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
        manual_capture: VerifiedManualCapture | None = None
        if local_suggestions is not None:
            try:
                manual_capture = await _manual_capture_snapshot(
                    client, context, candidate_handle, missing_is_none=True
                )
            except SemanticCoreProblem as error:
                logging.getLogger(__name__).warning(
                    "authoring telemetry edit context unavailable: %s", type(error).__name__
                )
        try:
            edit = request.app.state.structured_candidate_edit_store.append(
                context.project_id,
                candidate_handle,
                context.actor_id,
                context.request_id,
                payload,
            )
        except CandidateEditConflict as error:
            raise SemanticCoreProblem(
                409, "CANDIDATE_EDIT_CONFLICT", "The candidate edit revision is stale"
            ) from error
        if local_suggestions is not None and manual_capture is not None:
            try:
                dimensions, semantic_edit_count, unclassified = _manual_edit_telemetry(payload)
                local_suggestions.record_manual_edit(
                    _manual_capture_workflow_key(context, candidate_handle, manual_capture),
                    context.actor_id,
                    edit.edit_handle,
                    dimensions,
                    semantic_edit_count,
                    unclassified,
                    now=datetime.fromisoformat(edit.created_at),
                )
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "authoring telemetry edit hook failed safely: %s", type(error).__name__
                )
        response.headers["X-Request-Id"] = context.request_id
        return {
            "requestId": context.request_id,
            "candidateHandle": candidate_handle,
            "editHandle": edit.edit_handle,
            "revision": edit.revision,
            "corrections": edit.payload.model_dump(mode="json", by_alias=True, exclude_none=True),
            "provenance": {
                "actor": context.actor_id,
                "requestId": context.request_id,
                "recordedAt": edit.created_at,
            },
        }

    @router.get(
        "/v1/projects/{handle}/candidate-edit-options",
        response_model=CandidateEditOptionsResponse,
    )
    async def candidate_edit_options(
        handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> CandidateEditOptionsResponse:
        _require_selected_project_handle(request, handle)
        bounded = await client.entity_link_context(context, limit=100)
        entity_links = [
            CandidateEditOption(
                handle=str(required(mapping(item), "id")),
                label=str(required(mapping(item), "label")),
                type=str(required(mapping(item), "type")),
            )
            for item in bounded
        ]
        assignments = [
            CandidateEditOption(
                handle=opaque_navigation_handle(context.actor_id, "actor"),
                label="Current reviewer",
                type="Person",
            )
        ]
        response.headers["X-Request-Id"] = context.request_id
        return CandidateEditOptionsResponse(
            requestId=context.request_id,
            entityLinks=entity_links,
            assignments=assignments,
        )

    @router.get("/v1/projects/{handle}/graph", response_model=GraphProjectionResponse)
    async def project_graph(
        handle: str,
        context: Context,
        request: Request,
        response: Response,
        node_limit: Annotated[int, Query(alias="nodeLimit", ge=1, le=100)] = 50,
        edge_limit: Annotated[int, Query(alias="edgeLimit", ge=1, le=200)] = 100,
        semantic_types: Annotated[str | None, Query(alias="semanticTypes", max_length=500)] = None,
        verification_states: Annotated[
            str | None, Query(alias="verificationStates", max_length=200)
        ] = None,
        lifecycle_states: Annotated[
            str | None, Query(alias="lifecycleStates", max_length=300)
        ] = None,
        provenance_states: Annotated[
            str | None, Query(alias="provenanceStates", max_length=300)
        ] = None,
        relation_types: Annotated[str | None, Query(alias="relationTypes", max_length=500)] = None,
        evidence: Annotated[str, Query(pattern="^(any|with-evidence|without-evidence)$")] = "any",
        projection_revision: Annotated[
            str | None,
            Query(alias="projectionRevision", max_length=128, pattern="^[a-zA-Z0-9._-]+$"),
        ] = None,
    ) -> GraphProjectionResponse:
        _require_selected_project_handle(request, handle)
        filters = _graph_filters(
            semantic_types,
            verification_states,
            lifecycle_states,
            provenance_states,
            relation_types,
            evidence,
        )
        path = _core_query_path(
            f"/v1/projects/{context.project_id}/graph",
            {
                "nodeLimit": node_limit,
                "edgeLimit": edge_limit,
                **filters,
                "projectionRevision": projection_revision,
            },
        )
        raw = await client.request(context, "GET", path)
        result = project_graph_page(raw, context.request_id, handle, node_limit, edge_limit)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get(
        "/v1/projects/{handle}/graph/neighborhood/{node_handle}",
        response_model=GraphProjectionResponse,
    )
    async def project_neighborhood(
        handle: str,
        node_handle: str,
        context: Context,
        request: Request,
        response: Response,
        edge_limit: Annotated[int, Query(alias="edgeLimit", ge=1, le=100)] = 100,
        projection_revision: Annotated[
            str | None,
            Query(alias="projectionRevision", max_length=128, pattern="^[a-zA-Z0-9._-]+$"),
        ] = None,
    ) -> GraphProjectionResponse:
        _require_selected_project_handle(request, handle)
        _validate_handle(node_handle, ("node", "candidate", "knowledge"))
        raw = await client.request(
            context,
            "GET",
            _core_query_path(
                f"/v1/projects/{context.project_id}/graph/neighborhood/{node_handle}",
                {"edgeLimit": edge_limit, "projectionRevision": projection_revision},
            ),
        )
        result = project_graph_page(raw, context.request_id, handle, 50, edge_limit)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/projects/{handle}/graph/nodes/{node_handle}", response_model=GraphNodeDetail)
    async def graph_node_detail(
        handle: str,
        node_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> GraphNodeDetail:
        _require_selected_project_handle(request, handle)
        _validate_handle(node_handle, ("node", "candidate", "knowledge"))
        raw = await client.request(
            context,
            "GET",
            f"/v1/projects/{context.project_id}/graph/nodes/{node_handle}",
        )
        result = project_node_detail(raw, context.request_id, handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get(
        "/v1/projects/{handle}/graph/nodes/{node_handle}/evidence",
        response_model=GraphEvidenceResponse,
    )
    async def graph_node_evidence(
        handle: str,
        node_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> GraphEvidenceResponse:
        _require_selected_project_handle(request, handle)
        _validate_handle(node_handle, ("node", "candidate", "knowledge"))
        raw = await client.request(
            context,
            "GET",
            f"/v1/projects/{context.project_id}/graph/nodes/{node_handle}/evidence",
        )
        result = project_link_response(raw, context.request_id, handle, node_handle, "evidence")
        response.headers["X-Request-Id"] = context.request_id
        return cast(GraphEvidenceResponse, result)

    @router.get(
        "/v1/projects/{handle}/graph/nodes/{node_handle}/lifecycle",
        response_model=GraphLifecycleResponse,
    )
    async def graph_node_lifecycle(
        handle: str,
        node_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> GraphLifecycleResponse:
        _require_selected_project_handle(request, handle)
        _validate_handle(node_handle, ("node", "candidate", "knowledge"))
        raw = await client.request(
            context,
            "GET",
            f"/v1/projects/{context.project_id}/graph/nodes/{node_handle}/lifecycle",
        )
        result = project_link_response(raw, context.request_id, handle, node_handle, "lifecycle")
        response.headers["X-Request-Id"] = context.request_id
        return cast(GraphLifecycleResponse, result)

    @router.get("/v1/projects/{handle}/candidates", response_model=CandidateQueueResponse)
    async def candidate_queue(
        handle: str,
        context: Context,
        request: Request,
        response: Response,
        status: Annotated[
            str, Query(pattern="^(pending-review|validated|all)$")
        ] = "pending-review",
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> CandidateQueueResponse:
        _require_selected_project_handle(request, handle)
        raw = await client.request(
            context,
            "GET",
            _core_query_path(
                f"/v1/projects/{context.project_id}/candidates", {"status": status, "limit": limit}
            ),
        )
        result = project_candidate_queue(raw, context.request_id, handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get(
        "/v1/projects/{handle}/candidates/{candidate_handle}/review-detail",
        response_model=ReviewWorkbenchDetailResponse,
    )
    async def review_candidate_detail(
        handle: str,
        candidate_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> ReviewWorkbenchDetailResponse:
        """Return an authorized, source-first detail without forwarding Core payloads."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
        raw_queue = await client.request(
            context,
            "GET",
            _core_query_path(
                f"/v1/projects/{context.project_id}/candidates", {"status": "pending-review", "limit": 100}
            ),
        )
        queue = mapping(raw_queue)
        selected: dict[str, object] | None = None
        for item in required_list(queue, "candidates"):
            row = mapping(item)
            raw_handle = row.get("handle")
            projected = (
                raw_handle
                if isinstance(raw_handle, str) and raw_handle == candidate_handle
                else opaque_navigation_handle(raw_handle, "candidate")
                if isinstance(raw_handle, str)
                else None
            )
            if projected == candidate_handle:
                selected = row
                break
        if selected is None:
            raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The candidate is not visible in this project")
        detail_raw = {
            **selected,
            "sourceRevision": queue.get("sourceRevision", "source-unavailable"),
            "stale": queue.get("stale", False),
        }
        try:
            evidence_raw = await client.request(
                context,
                "GET",
                f"/v1/projects/{context.project_id}/graph/nodes/{candidate_handle}/evidence",
            )
            evidence = mapping(evidence_raw)
            if "items" in evidence:
                detail_raw["evidence"] = {
                    "status": "selected" if evidence.get("items") else "unavailable",
                    "highlights": evidence.get("items", []),
                }
        except SemanticCoreProblem:
            # Detail remains usable with an explicit unavailable evidence state.
            pass
        manual_capture = await _manual_capture_snapshot(
            client, context, candidate_handle, missing_is_none=True
        )
        if manual_capture is not None:
            detail_raw.update(
                _manual_capture_review_fields(
                    context.project_id,
                    selected.get("handle"),
                    manual_capture,
                )
            )
        receipt = _latest_review_receipt(extraction, context, selected.get("handle"))
        if receipt is not None:
            detail_raw["reviewReceipt"] = receipt
        result = project_review_detail(detail_raw, context.request_id, handle, candidate_handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/manual-approvals",
        response_model=ManualCaptureApprovalResponse,
    )
    async def approve_manual_candidate(
        handle: str,
        candidate_handle: str,
        payload: ManualCaptureApprovalRequest,
        context: Context,
        request: Request,
        idempotency_key: Key,
        response: Response,
    ) -> ManualCaptureApprovalResponse:
        """Record explicit approval for a verified manual Note without bypassing RM-63."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        receipt_service = _require_dependency(extraction, "review receipt persistence")
        capture = await _manual_capture_snapshot(
            client, context, candidate_handle, missing_is_none=False
        )
        if capture is None:
            raise SemanticCoreProblem(
                404, "RESOURCE_NOT_FOUND", "The manual candidate is not visible in this project"
            )
        if capture.candidate_status != "validated":
            raise SemanticCoreProblem(
                409, "MANUAL_CAPTURE_NOT_VALIDATED", "Validate this Note item before approval"
            )
        if (
            payload.candidate_revision != capture.candidate_revision
            or payload.expected_candidate_revision != 0
            or payload.source_version_id != capture.source_version.source_version_id
            or payload.source_version_revision != 1
            or payload.anchor_quote_digest != capture.anchor.quote_digest
        ):
            raise SemanticCoreProblem(
                409, "REVIEW_RECEIPT_STALE", "The manual source revision or anchor is stale"
            )
        actor = ReviewActorContext(
            project_id=context.project_id,
            actor_id=context.actor_id,
            capability="candidate.review",
            authorization_revision="trusted-context.v1",
        )
        decision_digest = "sha256:" + sha256(
            (
                "manual-entity-capture.v1|"
                + capture.entity_type
                + "|"
                + capture.source_version.source_version_id
                + "|"
                + capture.anchor.quote_digest
                + f"|{capture.anchor.start_offset}|{capture.anchor.end_offset}"
            ).encode("utf-8")
        ).hexdigest()
        receipt_request = _manual_capture_receipt_request(
            context.project_id,
            candidate_handle,
            capture,
            idempotency_key,
            "confirm",
            decision_digest,
        )
        try:
            receipt = receipt_service.record_review_decision(context, actor, receipt_request)
        except ReviewReceiptStaleError as error:
            raise SemanticCoreProblem(
                409, "REVIEW_RECEIPT_STALE", "The review source or candidate revision is stale"
            ) from error
        except (ReviewReceiptConflict, IdempotencyConflict, RevisionConflict) as error:
            raise SemanticCoreProblem(
                409, "REVIEW_RECEIPT_CONFLICT", "The review receipt conflicts with existing history"
            ) from error
        except (RuntimeError, ValueError) as error:
            raise SemanticCoreProblem(
                403, "REVIEW_UNAUTHORIZED", "The reviewer is not authorized for this item"
            ) from error
        if local_suggestions is not None:
            try:
                local_suggestions.record_manual_review(
                    _manual_capture_workflow_key(context, candidate_handle, capture),
                    context.actor_id,
                    receipt,
                )
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "authoring telemetry manual review hook failed safely: %s",
                    type(error).__name__,
                )
        response.status_code = 200 if receipt.outcome == "replayed" else 201
        response.headers["X-Request-Id"] = context.request_id
        return ManualCaptureApprovalResponse(
            contractVersion="manual-capture-approval.v1",
            requestId=context.request_id,
            outcome=receipt.outcome,
            receipt=receipt,
            materializationState="blocked",
            reasonCode="MATERIALIZATION_NOT_AUTHORIZED",
        )

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/manual-rejections",
        response_model=ManualCaptureRejectionResponse,
    )
    async def reject_manual_candidate(
        handle: str,
        candidate_handle: str,
        payload: ManualCaptureRejectionRequest,
        context: Context,
        request: Request,
        idempotency_key: Key,
        response: Response,
    ) -> ManualCaptureRejectionResponse:
        """Record a source-bound RM-61 rejection without mutating Semantic Core."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        receipt_service = _require_dependency(extraction, "review receipt persistence")
        capture = await _manual_capture_snapshot(
            client, context, candidate_handle, missing_is_none=False
        )
        if (
            payload.candidate_revision != capture.candidate_revision
            or payload.expected_candidate_revision != 0
            or payload.source_version_id != capture.source_version.source_version_id
            or payload.source_version_revision != 1
            or payload.anchor_quote_digest != capture.anchor.quote_digest
        ):
            raise SemanticCoreProblem(
                409, "REVIEW_RECEIPT_STALE", "The manual source revision or anchor is stale"
            )
        actor = ReviewActorContext(
            project_id=context.project_id,
            actor_id=context.actor_id,
            capability="candidate.review",
            authorization_revision="trusted-context.v1",
        )
        decision_digest = "sha256:" + sha256(
            (
                "manual-entity-reject.v1|"
                + capture.source_version.source_version_id
                + "|"
                + capture.anchor.quote_digest
                + "|"
                + payload.reason
            ).encode("utf-8")
        ).hexdigest()
        receipt_request = _manual_capture_receipt_request(
            context.project_id,
            candidate_handle,
            capture,
            idempotency_key,
            "reject",
            decision_digest,
        )
        try:
            receipt = receipt_service.record_review_decision(
                context, actor, receipt_request
            )
        except ReviewReceiptStaleError as error:
            raise SemanticCoreProblem(
                409, "REVIEW_RECEIPT_STALE", "The review source or candidate revision is stale"
            ) from error
        except (ReviewReceiptConflict, IdempotencyConflict, RevisionConflict) as error:
            raise SemanticCoreProblem(
                409, "REVIEW_RECEIPT_CONFLICT", "The review receipt conflicts with existing history"
            ) from error
        except (RuntimeError, ValueError) as error:
            raise SemanticCoreProblem(
                403, "REVIEW_UNAUTHORIZED", "The reviewer is not authorized for this item"
            ) from error
        if local_suggestions is not None:
            try:
                local_suggestions.record_manual_review(
                    _manual_capture_workflow_key(context, candidate_handle, capture),
                    context.actor_id,
                    receipt,
                )
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "authoring telemetry manual review hook failed safely: %s",
                    type(error).__name__,
                )
        response.status_code = 200 if receipt.outcome == "replayed" else 201
        response.headers["X-Request-Id"] = context.request_id
        return ManualCaptureRejectionResponse(
            contractVersion="manual-capture-decision.v1",
            requestId=context.request_id,
            decision="rejected",
            outcome=receipt.outcome,
            receipt=receipt,
        )

    @router.get(
        "/v1/projects/{handle}/authoring-metrics",
        response_model=AuthoringCostMetrics,
    )
    async def authoring_cost_metrics(
        handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> AuthoringCostMetrics:
        """Read user- and project-scoped digest-only authoring metrics."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        service = _require_local_suggestion_service(local_suggestions)
        result = service.authoring_metrics(context.project_id, context.actor_id)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get(
        "/v1/projects/{handle}/candidates/{candidate_handle}/local-suggestions",
        response_model=LocalSuggestionResponse,
    )
    async def local_suggestion_state(
        handle: str,
        candidate_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> LocalSuggestionResponse:
        """Read cached suggestion and remaining budgets without invoking inference."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        service = _require_local_suggestion_service(local_suggestions)
        subject, link_options = await _local_suggestion_subject(
            client, extraction, context, candidate_handle
        )
        result = service.read(subject.key, context.actor_id, link_options)
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/local-suggestions",
        response_model=LocalSuggestionResponse,
    )
    async def request_local_suggestion(
        handle: str,
        candidate_handle: str,
        payload: LocalSuggestionRequest,
        context: Context,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ) -> LocalSuggestionResponse:
        """Make at most one local inference call after a current human confirmation."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        service = _require_local_suggestion_service(local_suggestions)
        subject, link_options = await _local_suggestion_subject(
            client, extraction, context, candidate_handle
        )
        try:
            result = await service.request(
                subject,
                context.actor_id,
                idempotency_key,
                retry=payload.retry,
                link_options=link_options,
            )
        except LocalSuggestionError as error:
            raise _local_suggestion_problem(error) from error
        except LocalSuggestionStoreConflict as error:
            raise SemanticCoreProblem(
                409, "LOCAL_SUGGESTION_CONFLICT", "The suggestion request is stale or conflicting"
            ) from error
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/local-suggestions/"
        "{suggestion_id}/decisions",
        response_model=LocalSuggestionResponse,
    )
    async def decide_local_suggestion(
        handle: str,
        candidate_handle: str,
        suggestion_id: str,
        payload: LocalSuggestionDecisionRequest,
        context: Context,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ) -> LocalSuggestionResponse:
        """Record an explicit proposal decision; never materialize an assertion."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        service = _require_local_suggestion_service(local_suggestions)
        subject, link_options = await _local_suggestion_subject(
            client, extraction, context, candidate_handle
        )
        actor = _local_suggestion_actor(context)
        receipt_service = _require_dependency(extraction, "review receipt persistence")
        receipt_handle = _local_suggestion_receipt_handle(context.project_id, suggestion_id)
        history = receipt_service.review_decision_history(context, actor, "entity", receipt_handle)
        decision_digest = _local_suggestion_decision_digest(payload)
        prior = next(
            (
                item
                for item in history
                if item.idempotency_digest
                == "sha256:" + sha256(idempotency_key.encode("utf-8", "strict")).hexdigest()
            ),
            None,
        )
        current = service.read(subject.key, context.actor_id, link_options)
        if current.suggestion is None or current.suggestion.suggestion_id != suggestion_id:
            raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The suggestion is not visible")
        if prior is not None:
            receipt_request = _local_suggestion_receipt_request(
                context,
                subject,
                receipt_handle,
                idempotency_key,
                payload.decision,
                decision_digest,
                prior.candidate_revision,
                prior.previous_decision_digest,
            )
            try:
                receipt = receipt_service.record_review_decision(context, actor, receipt_request)
            except (ReviewReceiptConflict, ReviewReceiptStaleError, IdempotencyConflict, RevisionConflict) as error:
                raise SemanticCoreProblem(
                    409, "LOCAL_SUGGESTION_CONFLICT", "The suggestion decision conflicts with its receipt"
                ) from error
            response.headers["X-Request-Id"] = context.request_id
            return current.model_copy(update={"request_id": context.request_id, "receipt": receipt})
        if (
            current.state not in {"proposed", "edited"}
            or current.suggestion.revision != payload.expected_revision
        ):
            raise SemanticCoreProblem(
                409, "LOCAL_SUGGESTION_STALE", "The proposal revision is stale or no longer pending"
            )
        if payload.decision == "confirm" and current.suggestion.kind == "link":
            if not any(
                option.handle == current.suggestion.target_handle
                and option.label == current.suggestion.target_label
                for option in link_options
            ):
                raise SemanticCoreProblem(
                    409,
                    "LOCAL_SUGGESTION_TARGET_STALE",
                    "The same-project link target is no longer visible.",
                )
        edited_proposal = None
        if payload.decision == "edit":
            if payload.edit is None:
                raise SemanticCoreProblem(
                    422, "LOCAL_SUGGESTION_EDIT_INVALID", "An edit must match the proposal kind"
                )
            try:
                edited_proposal = service.prepare_edit(
                    subject.key,
                    context.actor_id,
                    payload.expected_revision,
                    payload.edit,
                    link_options,
                )
            except LocalSuggestionStoreConflict as error:
                raise SemanticCoreProblem(
                    422, "LOCAL_SUGGESTION_EDIT_INVALID", "The edit is outside the confirmed project context"
                ) from error
        previous = max(history, key=lambda item: item.sequence) if history else None
        receipt_revision = previous.candidate_revision + 1 if previous else 1
        receipt_request = _local_suggestion_receipt_request(
            context,
            subject,
            receipt_handle,
            idempotency_key,
            payload.decision,
            decision_digest,
            receipt_revision,
            previous.receipt_digest if previous else None,
        )
        try:
            receipt = receipt_service.record_review_decision(context, actor, receipt_request)
            result = service.decide(
                subject.key,
                context.actor_id,
                payload.expected_revision,
                payload.decision,
                edited_proposal,
                link_options,
                receipt,
            )
        except (ReviewReceiptConflict, ReviewReceiptStaleError, IdempotencyConflict, RevisionConflict) as error:
            raise SemanticCoreProblem(
                409, "LOCAL_SUGGESTION_CONFLICT", "The suggestion decision conflicts with its receipt"
            ) from error
        except LocalSuggestionStoreConflict as error:
            raise SemanticCoreProblem(
                409, "LOCAL_SUGGESTION_STALE", "The proposal revision changed before the decision"
            ) from error
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.get(
        "/v1/projects/{handle}/candidates/{candidate_handle}/relation-suggestion-targets",
        response_model=RelationSuggestionTargetsResponse,
    )
    async def relation_suggestion_targets(
        handle: str,
        candidate_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> RelationSuggestionTargetsResponse:
        """List same-project, current-confirmed manual endpoints with deterministic evidence."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        receipt_service = _require_dependency(extraction, "review receipt persistence")
        selected = await _controlled_relation_endpoint(
            client, receipt_service, context, candidate_handle
        )
        raw_queue = await client.request(
            context,
            "GET",
            _core_query_path(
                f"/v1/projects/{context.project_id}/candidates",
                {"status": "all", "limit": 100},
            ),
        )
        directions: tuple[RelationDirection, ...] = (
            "source-to-target",
            "target-to-source",
        )
        targets: list[RelationSuggestionTarget] = []
        seen: set[str] = set()
        for value in required_list(mapping(raw_queue), "candidates"):
            row = mapping(value)
            raw_handle = row.get("handle")
            if not isinstance(raw_handle, str) or not raw_handle:
                continue
            target_handle = opaque_or_hashed(raw_handle, "candidate")
            if target_handle == candidate_handle or target_handle in seen:
                continue
            seen.add(target_handle)
            capture = await _manual_capture_snapshot(
                client, context, target_handle, missing_is_none=True
            )
            if capture is None:
                continue
            try:
                target = _controlled_relation_endpoint_from_capture(
                    receipt_service, context, target_handle, capture
                )
            except SemanticCoreProblem as error:
                if error.code in {
                    "CONTROLLED_RELATION_REQUIRES_CONFIRMATION",
                    "CONTROLLED_RELATION_REQUIRES_VALIDATION",
                }:
                    continue
                raise
            allowed: dict[RelationDirection, list[str]] = {}
            for direction in directions:
                try:
                    suggestion_context = build_relation_suggestion_context(
                        context.project_id, selected, target, direction
                    )
                except ValueError:
                    allowed[direction] = []
                else:
                    allowed[direction] = list(suggestion_context.allowed_predicates)
            if not any(allowed.values()):
                continue
            targets.append(
                RelationSuggestionTarget(
                    candidateHandle=target_handle,
                    label=capture.evidence_text,
                    entityType=capture.entity_type,
                    allowedPredicates=allowed,
                )
            )
        response.headers["X-Request-Id"] = context.request_id
        return RelationSuggestionTargetsResponse(
            requestId=context.request_id, targets=targets
        )

    @router.get(
        "/v1/projects/{handle}/candidates/{candidate_handle}/relation-suggestions",
        response_model=LocalSuggestionResponse,
    )
    async def read_controlled_relation_suggestion(
        handle: str,
        candidate_handle: str,
        context: Context,
        request: Request,
        response: Response,
        target_candidate_handle: Annotated[
            str, Query(alias="targetCandidateHandle", min_length=1, max_length=128)
        ],
        direction: RelationDirection,
        mode: RelationSuggestionMode,
        predicate: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    ) -> LocalSuggestionResponse:
        """Read current pair-specific suggestion state without invoking inference."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        _validate_handle(target_candidate_handle, ("candidate",))
        if (mode == "manual") != (predicate is not None):
            raise SemanticCoreProblem(
                422, "CONTROLLED_RELATION_REQUEST_INVALID", "Select a predicate only for manual mode."
            )
        service = _require_local_suggestion_service(local_suggestions)
        subject, link_options = await _controlled_relation_subject(
            client,
            extraction,
            context,
            candidate_handle,
            target_candidate_handle,
            direction,
            mode,
            predicate,
        )
        relation = subject.relation_context
        if relation is None:
            raise SemanticCoreProblem(
                503, "CONTROLLED_RELATION_UNAVAILABLE", "The relation context is unavailable"
            )
        if mode == "manual" and predicate not in allowed_relation_predicates(
            relation.source_type, relation.target_type
        ):
            raise SemanticCoreProblem(
                422,
                "CONTROLLED_RELATION_UNSUPPORTED",
                "The predicate is not allowed for these endpoint types and direction.",
            )
        result = service.read(subject.key, context.actor_id, link_options)
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/relation-suggestions",
        response_model=LocalSuggestionResponse,
    )
    async def request_controlled_relation_suggestion(
        handle: str,
        candidate_handle: str,
        payload: ControlledRelationRequest,
        context: Context,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ) -> LocalSuggestionResponse:
        """Create a server-evidenced relation proposal from two confirmed endpoints."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        _validate_handle(payload.target_candidate_handle, ("candidate",))
        service = _require_local_suggestion_service(local_suggestions)
        subject, link_options = await _controlled_relation_subject(
            client,
            extraction,
            context,
            candidate_handle,
            payload.target_candidate_handle,
            payload.direction,
            payload.mode,
            payload.predicate,
        )
        relation = subject.relation_context
        if relation is None:
            raise SemanticCoreProblem(
                503, "CONTROLLED_RELATION_UNAVAILABLE", "The relation context is unavailable"
            )
        try:
            if payload.mode == "manual":
                permitted = allowed_relation_predicates(
                    relation.source_type, relation.target_type
                )
                if payload.predicate not in permitted:
                    raise SemanticCoreProblem(
                        422,
                        "CONTROLLED_RELATION_UNSUPPORTED",
                        "The predicate is not allowed for these endpoint types and direction.",
                    )
                option = relation.option_for(payload.predicate or "")
                if option is None:
                    raise SemanticCoreProblem(
                        409,
                        "CONTROLLED_RELATION_EVIDENCE_UNAVAILABLE",
                        "No current deterministic evidence supports this relation.",
                    )
                proposal = _controlled_relation_proposal(relation, option, "manual")
                result = service.propose_manual(
                    subject.key, context.actor_id, proposal, link_options
                )
            else:
                if not relation.allowed_predicates:
                    raise SemanticCoreProblem(
                        409,
                        "CONTROLLED_RELATION_UNSUPPORTED",
                        "No allowlisted relation predicate has deterministic evidence.",
                    )
                result = await service.request(
                    subject,
                    context.actor_id,
                    idempotency_key,
                    retry=payload.retry,
                    link_options=link_options,
                )
        except LocalSuggestionError as error:
            raise _local_suggestion_problem(error) from error
        except LocalSuggestionStoreConflict as error:
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_CONFLICT",
                "The relation suggestion is stale or conflicting.",
            ) from error
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.get(
        "/v1/projects/{handle}/candidates/{candidate_handle}/relation-suggestions/"
        "{suggestion_id}",
        response_model=LocalSuggestionResponse,
    )
    async def controlled_relation_suggestion_state(
        handle: str,
        candidate_handle: str,
        suggestion_id: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> LocalSuggestionResponse:
        """Read and revalidate the stored relation proposal without invoking inference."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        service = _require_local_suggestion_service(local_suggestions)
        result, _subject, _proposal = await _controlled_relation_state(
            client,
            extraction,
            service,
            context,
            candidate_handle,
            suggestion_id,
        )
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/relation-suggestions/"
        "{suggestion_id}/decisions",
        response_model=LocalSuggestionResponse,
    )
    async def decide_controlled_relation_suggestion(
        handle: str,
        candidate_handle: str,
        suggestion_id: str,
        payload: ControlledRelationDecisionRequest,
        context: Context,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ) -> LocalSuggestionResponse:
        """Append an explicit relation confirm/reject receipt after stale-anchor checks."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate",))
        service = _require_local_suggestion_service(local_suggestions)
        current, subject, proposal = await _controlled_relation_state(
            client,
            extraction,
            service,
            context,
            candidate_handle,
            suggestion_id,
        )
        if proposal.kind != "relation" or proposal.relation_id is None:
            raise SemanticCoreProblem(
                409, "CONTROLLED_RELATION_NOT_DECIDABLE", "This suggestion has no relation to decide."
            )
        relation_evidence_digest = proposal.relation_evidence_digest
        if relation_evidence_digest is None:
            raise SemanticCoreProblem(
                409, "CONTROLLED_RELATION_STALE", "The relation evidence digest is unavailable."
            )
        actor = _local_suggestion_actor(context)
        receipt_service = _require_dependency(extraction, "review receipt persistence")
        try:
            history = receipt_service.review_decision_history(
                context, actor, "relation", proposal.relation_id
            )
        except (RuntimeError, ValueError) as error:
            raise SemanticCoreProblem(
                503,
                "REVIEW_RECEIPTS_UNAVAILABLE",
                "The relation review receipt is unavailable.",
            ) from error
        decision_digest = _controlled_relation_decision_digest(payload)
        idempotency_digest = "sha256:" + sha256(
            idempotency_key.encode("utf-8", "strict")
        ).hexdigest()
        prior = next(
            (item for item in history if item.idempotency_digest == idempotency_digest),
            None,
        )
        if prior is not None:
            receipt_request = _controlled_relation_receipt_request(
                context,
                subject.key,
                proposal.relation_id,
                relation_evidence_digest,
                idempotency_key,
                payload.decision,
                decision_digest,
                prior.candidate_revision,
                prior.candidate_revision - 1,
                prior.previous_decision_digest,
            )
            try:
                receipt = receipt_service.record_review_decision(
                    context, actor, receipt_request
                )
            except (ReviewReceiptConflict, ReviewReceiptStaleError, IdempotencyConflict, RevisionConflict) as error:
                raise SemanticCoreProblem(
                    409,
                    "CONTROLLED_RELATION_CONFLICT",
                    "The relation decision conflicts with its receipt.",
                ) from error
            response.headers["X-Request-Id"] = context.request_id
            return current.model_copy(
                update={"request_id": context.request_id, "receipt": receipt}
            )
        if history:
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_STALE",
                "A decision receipt already exists for this relation.",
            )
        if (
            current.state != "proposed"
            or current.suggestion is None
            or current.suggestion.revision != payload.expected_revision
        ):
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_STALE",
                "The relation proposal revision is stale or no longer pending.",
            )
        receipt_request = _controlled_relation_receipt_request(
            context,
            subject.key,
            proposal.relation_id,
            relation_evidence_digest,
            idempotency_key,
            payload.decision,
            decision_digest,
            1,
            0,
            None,
        )
        try:
            receipt = receipt_service.record_review_decision(
                context, actor, receipt_request
            )
            result = service.decide(
                subject.key,
                context.actor_id,
                payload.expected_revision,
                payload.decision,
                None,
                [],
                receipt,
            )
        except (ReviewReceiptConflict, ReviewReceiptStaleError, IdempotencyConflict, RevisionConflict) as error:
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_CONFLICT",
                "The relation decision conflicts with its receipt.",
            ) from error
        except LocalSuggestionStoreConflict as error:
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_STALE",
                "The relation proposal changed before the decision.",
            ) from error
        response.headers["X-Request-Id"] = context.request_id
        return result.model_copy(update={"request_id": context.request_id})

    @router.post(
        "/v1/projects/{handle}/candidates/{candidate_handle}/abstentions",
        response_model=ReviewAbstainResponse,
    )
    async def abstain_selected_candidate(
        handle: str,
        candidate_handle: str,
        payload: ReviewAbstainRequest,
        context: Context,
        request: Request,
        idempotency_key: Key,
        response: Response,
    ) -> ReviewAbstainResponse:
        """Append an RM-61 abstain receipt after resolving the selected item server-side."""

        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
        if extraction is None:
            raise SemanticCoreProblem(503, "REVIEW_RECEIPT_UNAVAILABLE", "Review receipt persistence is unavailable")
        manual_capture = await _manual_capture_snapshot(
            client, context, candidate_handle, missing_is_none=True
        )
        if manual_capture is not None:
            if (
                payload.candidate_revision != manual_capture.candidate_revision
                or payload.expected_candidate_revision != 0
                or payload.source_version_id
                != manual_capture.source_version.source_version_id
                or payload.source_version_revision != 1
                or payload.constrained_contract_version
                != "manual-entity-capture.v1"
                or payload.evidence_digest != manual_capture.anchor.quote_digest
                or payload.previous_decision_digest is not None
            ):
                raise SemanticCoreProblem(
                    409, "REVIEW_RECEIPT_STALE", "The manual source revision or anchor is stale"
                )
            actor = ReviewActorContext(
                project_id=context.project_id,
                actor_id=context.actor_id,
                capability="candidate.review",
                authorization_revision="trusted-context.v1",
            )
            receipt_request = _manual_capture_receipt_request(
                context.project_id,
                candidate_handle,
                manual_capture,
                idempotency_key,
                "abstain",
                None,
            )
            try:
                receipt = extraction.record_review_decision(
                    context, actor, receipt_request
                )
            except ReviewReceiptStaleError as error:
                raise SemanticCoreProblem(
                    409, "REVIEW_RECEIPT_STALE", "The review receipt revision is stale"
                ) from error
            except (ReviewReceiptConflict, IdempotencyConflict, RevisionConflict) as error:
                raise SemanticCoreProblem(
                    409, "REVIEW_RECEIPT_CONFLICT", "The review receipt conflicts with existing history"
                ) from error
            except (RuntimeError, ValueError) as error:
                raise SemanticCoreProblem(
                    403, "REVIEW_UNAUTHORIZED", "The reviewer is not authorized for this item"
                ) from error
            response.status_code = 200 if receipt.outcome == "replayed" else 201
            response.headers["X-Request-Id"] = context.request_id
            return ReviewAbstainResponse(
                contractVersion="review-receipt.v1",
                requestId=context.request_id,
                decision="abstain",
                outcome=receipt.outcome,
                receipt=receipt,
            )

        raw_queue = await client.request(
            context,
            "GET",
            _core_query_path(
                f"/v1/projects/{context.project_id}/candidates",
                {"status": "pending-review", "limit": 100},
            ),
        )
        selected = _resolve_review_candidate(raw_queue, candidate_handle)
        if selected is None:
            raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The candidate is not visible in this project")
        raw_handle = selected.get("handle")
        if not isinstance(raw_handle, str) or not raw_handle:
            raise SemanticCoreProblem(409, "REVIEW_ITEM_INVALID", "The selected review item has no server handle")
        source = mapping(selected.get("sourceVersion", {}))
        source_version_id = source.get("sourceVersionId", source.get("id"))
        source_revision = source.get("revision")
        candidate_revision = selected.get("candidateRevision", selected.get("revision"))
        if (
            not isinstance(source_version_id, str)
            or not source_version_id.startswith("sv_")
            or len(source_version_id) != 67
            or not isinstance(source_revision, int)
            or source_revision < 1
            or not isinstance(candidate_revision, int)
            or candidate_revision < 1
        ):
            raise SemanticCoreProblem(
                409,
                "REVIEW_SOURCE_RECEIPT_UNAVAILABLE",
                "The selected item is missing a verified SourceVersion receipt",
            )
        if payload.source_version_id != source_version_id or payload.source_version_revision != source_revision:
            raise SemanticCoreProblem(409, "REVIEW_RECEIPT_STALE", "The source version is stale")
        if payload.candidate_revision != candidate_revision:
            raise SemanticCoreProblem(409, "REVIEW_RECEIPT_STALE", "The candidate revision is stale")
        selected_evidence = mapping(selected.get("evidence", {}))
        selected_evidence_digest = selected_evidence.get("digest")
        if isinstance(selected_evidence_digest, str) and payload.evidence_digest != selected_evidence_digest:
            raise SemanticCoreProblem(409, "REVIEW_RECEIPT_STALE", "The evidence digest is stale")
        selected_contract = selected.get("constrainedContractVersion")
        if isinstance(selected_contract, str) and payload.constrained_contract_version != selected_contract:
            raise SemanticCoreProblem(409, "REVIEW_RECEIPT_STALE", "The constrained contract is stale")
        actor = ReviewActorContext(
            project_id=context.project_id,
            actor_id=context.actor_id,
            capability="candidate.review",
            authorization_revision="trusted-context.v1",
        )
        receipt_request = ReviewDecisionRequest(
            projectId=context.project_id,
            itemKind="entity",
            itemHandle=_review_receipt_handle(context.project_id, raw_handle),
            candidateRevision=payload.candidate_revision,
            expectedCandidateRevision=payload.expected_candidate_revision,
            sourceVersionId=payload.source_version_id,
            sourceVersionRevision=payload.source_version_revision,
            constrainedContractVersion=payload.constrained_contract_version,
            evidenceDigest=payload.evidence_digest,
            previousDecisionDigest=payload.previous_decision_digest,
            idempotencyKey=idempotency_key,
            decision="abstain",
        )
        try:
            receipt = extraction.record_review_decision(context, actor, receipt_request)
        except ReviewReceiptStaleError as error:
            raise SemanticCoreProblem(409, "REVIEW_RECEIPT_STALE", "The review receipt revision is stale") from error
        except (ReviewReceiptConflict, IdempotencyConflict, RevisionConflict) as error:
            raise SemanticCoreProblem(409, "REVIEW_RECEIPT_CONFLICT", "The review receipt conflicts with existing history") from error
        except (RuntimeError, ValueError) as error:
            raise SemanticCoreProblem(403, "REVIEW_UNAUTHORIZED", "The reviewer is not authorized for this item") from error
        response.headers["X-Request-Id"] = context.request_id
        return ReviewAbstainResponse(
            contractVersion="review-receipt.v1",
            requestId=context.request_id,
            decision="abstain",
            outcome=receipt.outcome,
            receipt=receipt,
        )

    @router.post("/v1/projects/{handle}/candidates/{candidate_handle}/validations")
    async def validate_selected_candidate(
        handle: str,
        candidate_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> object:
        require_capability(request, context, "candidate.validate")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
        result = await client.request(
            context,
            "POST",
            f"/v1/projects/{context.project_id}/candidates/{candidate_handle}/validations",
        )
        result = _preserve_core_status(response, result)
        raw_result = mapping(result)
        edit = request.app.state.structured_candidate_edit_store.latest(
            context.project_id, candidate_handle
        )
        raw_result["correctionRevision"] = edit.revision if edit is not None else 0
        raw_result["corrections"] = (
            edit.payload.model_dump(mode="json", by_alias=True, exclude_none=True)
            if edit is not None
            else {}
        )
        raw_result["correctionsValidated"] = True
        result = raw_result
        result = _id_free_payload(result, context.request_id, handle, candidate_handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/projects/{handle}/candidates/{candidate_handle}/confirmations")
    async def confirm_selected_candidate(
        handle: str,
        candidate_handle: str,
        payload: ConfirmationRequest,
        context: Context,
        request: Request,
        idempotency_key: Key,
        response: Response,
    ) -> object:
        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
        manual_capture = await _manual_capture_snapshot(
            client, context, candidate_handle, missing_is_none=True
        )
        if manual_capture is not None:
            raise SemanticCoreProblem(
                409,
                "MATERIALIZATION_NOT_AUTHORIZED",
                "Manual Note approval receipts cannot materialize assertions while RM-63 authorization is locked",
            )
        edit = request.app.state.structured_candidate_edit_store.latest(
            context.project_id, candidate_handle
        )
        corrected = _apply_candidate_correction(payload, edit)
        result = await client.request(
            context,
            "POST",
            f"/v1/projects/{context.project_id}/candidates/{candidate_handle}/confirmations",
            {"assertion": corrected.assertion.model_dump(mode="json", by_alias=True)},
            idempotency_key,
        )
        result = _preserve_core_status(response, result)
        raw_result = mapping(result)
        raw_result["appliedCorrectionRevision"] = edit.revision if edit is not None else 0
        result = raw_result
        result = _id_free_payload(result, context.request_id, handle, candidate_handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/projects/{handle}/candidates/{candidate_handle}/rejections")
    async def reject_selected_candidate(
        handle: str,
        candidate_handle: str,
        payload: RejectionRequest,
        context: Context,
        request: Request,
        idempotency_key: Key,
        response: Response,
    ) -> object:
        require_capability(request, context, "candidate.review")
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
        manual_capture = await _manual_capture_snapshot(
            client, context, candidate_handle, missing_is_none=True
        )
        if manual_capture is not None:
            raise SemanticCoreProblem(
                409,
                "REVIEW_RECEIPT_REQUIRED",
                "Manual Note rejection must use the source-bound receipt route",
            )

        result = await client.request(
            context,
            "POST",
            f"/v1/projects/{context.project_id}/candidates/{candidate_handle}/rejections",
            payload.model_dump(mode="json", by_alias=True),
            idempotency_key,
        )
        result = _preserve_core_status(response, result)
        result = _id_free_payload(result, context.request_id, handle, candidate_handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/projects/{handle}/knowledge", response_model=KnowledgeCollectionResponse)
    async def knowledge_collection(
        handle: str,
        context: Context,
        request: Request,
        response: Response,
        semantic_type: Annotated[
            str, Query(alias="type", pattern="^(Requirement|Decision|Question|Task|Risk)$")
        ] = "Requirement",
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> KnowledgeCollectionResponse:
        _require_selected_project_handle(request, handle)
        raw = await client.request(
            context,
            "GET",
            _core_query_path(
                f"/v1/projects/{context.project_id}/knowledge",
                {"type": semantic_type, "limit": limit},
            ),
        )
        result = project_knowledge_collection(raw, context.request_id, handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/projects/{handle}/knowledge/{item_handle}")
    async def knowledge_detail(
        handle: str,
        item_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> object:
        _require_selected_project_handle(request, handle)
        _validate_handle(item_handle, ("knowledge", "node"))
        raw = await client.request(
            context, "GET", f"/v1/projects/{context.project_id}/knowledge/{item_handle}"
        )
        result = _id_free_payload(raw, context.request_id, handle, item_handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/projects/{handle}/knowledge/{item_handle}/evidence")
    async def knowledge_evidence(
        handle: str,
        item_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> object:
        _require_selected_project_handle(request, handle)
        _validate_handle(item_handle, ("knowledge", "node"))
        raw = await client.request(
            context,
            "GET",
            f"/v1/projects/{context.project_id}/knowledge/{item_handle}/evidence",
        )
        result = _id_free_payload(raw, context.request_id, handle, item_handle)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/project-context/answers")
    async def project_context_answer(
        payload: ProjectContextQuestion, context: Context, response: Response
    ) -> object:
        answer = await _require_dependency(retrieval, "retrieval").answer(
            context, payload.question, payload.limit
        )
        response.headers["X-Request-Id"] = context.request_id
        return answer.model_dump(mode="json", by_alias=True)

    @router.post("/v1/project-context/inference/rebuild")
    async def rebuild_project_context(context: Context, response: Response) -> object:
        result = await client.request(context, "POST", "/v1/inference/rebuild")
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/settings/llm")
    async def read_llm_profile(context: Context, response: Response) -> object:
        profile = _require_dependency(configuration_service, "configuration").read(context)
        response.headers["X-Request-Id"] = context.request_id
        return {
            "requestId": context.request_id,
            "profile": profile.model_dump(mode="json", by_alias=True) if profile else None,
        }

    @router.put("/v1/settings/llm")
    async def write_llm_profile(
        payload: LLMProfileWrite, context: Context, response: Response
    ) -> object:
        profile = _require_dependency(configuration_service, "configuration").save(context, payload)
        response.headers["X-Request-Id"] = context.request_id
        return {
            "requestId": context.request_id,
            "profile": profile.model_dump(mode="json", by_alias=True),
        }

    @router.post("/v1/settings/llm/rotate")
    async def rotate_llm_credential(
        payload: LLMProfileWrite, context: Context, response: Response
    ) -> object:
        profile = _require_dependency(configuration_service, "configuration").rotate(
            context, payload
        )
        response.headers["X-Request-Id"] = context.request_id
        return {
            "requestId": context.request_id,
            "profile": profile.model_dump(mode="json", by_alias=True),
        }

    @router.delete("/v1/settings/llm")
    async def remove_llm_profile(
        payload: LLMProfileRemove, context: Context, response: Response
    ) -> object:
        profile = _require_dependency(configuration_service, "configuration").remove(
            context, payload
        )
        response.headers["X-Request-Id"] = context.request_id
        return {
            "requestId": context.request_id,
            "profile": profile.model_dump(mode="json", by_alias=True) if profile else None,
        }

    @router.post("/v1/settings/llm/connection-check")
    async def check_llm_connection(
        payload: ConnectionCheckRequest, context: Context, response: Response
    ) -> object:
        runtime = _require_dependency(runtime_configuration, "runtime configuration")
        checker = _require_dependency(connection_checker, "provider connection checker")
        started = datetime.now(UTC)
        try:
            snapshot = runtime.resolve_llm(context)
        except ConfigurationProblem:
            raise
        except Exception as error:
            from projecta_api.llm.gateway import NormalizedGatewayError

            if isinstance(error, NormalizedGatewayError):
                raise ConfigurationProblem(
                    "CONFIGURATION_UNAVAILABLE",
                    "The active LLM profile is unavailable.",
                    status_code=503,
                ) from error
            raise ConfigurationProblem(
                "CONFIGURATION_UNAVAILABLE",
                "The active LLM profile is unavailable.",
                status_code=503,
            ) from error
        result = await checker.check(snapshot, payload.timeout_seconds)
        if configuration_service is not None:
            configuration_service.record_connection_check(context, snapshot.revision, result)
        if configuration_audit is not None:
            configuration_audit.record(
                scope=context.project_id,
                actor_id=context.actor_id,
                request_id=context.request_id,
                operation="test",
                outcome=result.status,
                provider_type=snapshot.provider_type,
                base_url=snapshot.base_url,
                revision_before=int(snapshot.revision) if snapshot.revision.isdigit() else None,
                latency_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
            )
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, **result.model_dump(mode="json", by_alias=True)}

    @router.post("/v1/quick-notes/extractions")
    async def extract(
        payload: ExtractionRequest, context: Context, idempotency_key: Key, response: Response
    ) -> object:
        result = await _require_dependency(extraction, "extraction").extract(
            context, idempotency_key, payload
        )
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/quick-notes", response_model=CaptureResponse, status_code=201)
    async def capture(
        payload: CaptureRequest, context: Context, idempotency_key: Key, response: Response
    ) -> CaptureResponse:
        result = await client.capture(context, idempotency_key, payload)
        if result.replayed:
            response.status_code = 200
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/candidates/{candidate_id}/validations")
    async def validate(candidate_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "POST", f"/v1/candidates/{candidate_id}/validations")
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/candidates/{candidate_id}/confirmations")
    async def confirm(
        candidate_id: str,
        payload: ConfirmationRequest,
        context: Context,
        idempotency_key: Key,
        response: Response,
    ) -> object:
        result = await client.request(
            context,
            "POST",
            f"/v1/candidates/{candidate_id}/confirmations",
            {"assertion": payload.assertion.model_dump(mode="json", by_alias=True)},
            idempotency_key,
        )
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.post("/v1/candidates/{candidate_id}/rejections")
    async def reject(
        candidate_id: str,
        payload: RejectionRequest,
        context: Context,
        idempotency_key: Key,
        response: Response,
    ) -> object:
        result = await client.request(
            context,
            "POST",
            f"/v1/candidates/{candidate_id}/rejections",
            payload.model_dump(mode="json", by_alias=True),
            idempotency_key,
        )
        result = _preserve_core_status(response, result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/knowledge-items/current")
    async def current(context: Context, response: Response, type: str | None = None) -> object:
        suffix = "" if type is None else f"?type={type}"
        result = await client.request(context, "GET", f"/v1/knowledge-items/current{suffix}")
        result = _preserve_core_status(response, result)
        result = project_current_knowledge(result)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/candidates/{candidate_id}/history")
    async def history(candidate_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "GET", f"/v1/candidates/{candidate_id}/history")
        result = _preserve_core_status(response, result)
        result = project_candidate_history(result, candidate_id)
        response.headers["X-Request-Id"] = context.request_id
        return result

    @router.get("/v1/entities/link-context")
    async def entity_link_context(
        context: Context,
        response: Response,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> object:
        entities = await client.entity_link_context(context, limit)
        response.headers["X-Request-Id"] = context.request_id
        return {"requestId": context.request_id, "entities": entities}

    @router.get("/v1/knowledge-items/{item_id}/evidence")
    async def evidence(item_id: str, context: Context, response: Response) -> object:
        result = await client.request(context, "GET", f"/v1/knowledge-items/{item_id}/evidence")
        result = _preserve_core_status(response, result)
        result = project_evidence(result, item_id)
        response.headers["X-Request-Id"] = context.request_id
        return result

    add_connector_routes(router, connector_runtime)
    return router


def _catalog_ids(request: Request) -> tuple[str, ...]:
    """Read the explicit allowlist from the request app without exposing it publicly."""
    if not request.app.state.settings.experience_project_catalog.strip():
        raise SemanticCoreProblem(
            503, "PROJECT_CATALOG_UNAVAILABLE", "Project catalog is not configured"
        )
    try:
        return configured_project_ids(request.app.state.settings.experience_project_catalog)
    except ValueError as error:
        raise SemanticCoreProblem(
            503, "PROJECT_CATALOG_UNAVAILABLE", "Project catalog configuration is invalid"
        ) from error


async def _read_project_catalog(
    client: SemanticCoreClient,
    actor: TrustedActorContext,
    project_ids: tuple[str, ...],
    limit: int,
) -> tuple[ProjectCatalogResponse, list[dict[str, object]]]:
    raw = await client.project_catalog(actor, list(project_ids), limit)
    payload = mapping(raw)
    payload.pop("_projecta_http_status", None)
    projects = required_list(payload, "projects")
    internal = [mapping(item) for item in projects]
    mapped = [_map_catalog_item(item) for item in internal]
    revision = _required_string(payload, "catalogRevision")
    next_cursor = payload.get("nextCursor")
    if next_cursor is not None and not isinstance(next_cursor, str):
        raise ValueError("project catalog nextCursor is invalid")
    result = ProjectCatalogResponse(
        requestId=actor.request_id,
        catalogRevision=revision,
        projects=mapped,
        nextCursor=next_cursor,
    )
    return result, internal


def _map_catalog_item(item: dict[str, object]) -> ProjectCatalogItem:
    project_id = _required_string(item, "projectId")
    counts = mapping(required(item, "counts"))
    freshness = {
        "state": required(item, "freshnessState"),
        "revision": required(item, "freshnessRevision"),
    }
    return ProjectCatalogItem.model_validate(
        {
            "handle": opaque_project_handle(project_id),
            "name": required(item, "name"),
            "summary": item.get("summary"),
            "status": required(item, "status"),
            "counts": counts,
            "lastActivityAt": item.get("lastActivityAt"),
            "health": required(item, "health"),
            "freshness": freshness,
        }
    )


def _map_project_overview(request_id: str, raw: object, handle: str) -> dict[str, object]:
    payload = mapping(raw)
    project = mapping(required(payload, "project"))
    item = _map_catalog_item(project).model_dump(mode="json", by_alias=True)
    item.update(
        {
            "requestId": request_id,
            "currentRequirements": required_list(payload, "currentRequirements"),
            "openQuestions": required_list(payload, "openQuestions"),
            "tasks": required_list(payload, "tasks"),
            "blockers": required_list(payload, "blockers"),
            "risks": required_list(payload, "risks"),
            "recentNotes": required_list(payload, "recentNotes"),
            "pendingCandidates": required_list(payload, "pendingCandidates"),
            "evidenceCoverage": mapping(required(payload, "evidenceCoverage")),
        }
    )
    if item["handle"] != handle:
        raise _project_not_found()
    return item


def _project_not_found() -> SemanticCoreProblem:
    return SemanticCoreProblem(
        404, "PROJECT_NOT_FOUND", "The project is not visible in the authorized catalog"
    )


def _preserve_core_status(response: Response, result: object) -> object:
    """Forward a finite Core operation's success status without exposing metadata."""
    if isinstance(result, dict):
        mapping = cast(dict[str, object], result)
        status = mapping.pop("_projecta_http_status", 200)
        if isinstance(status, int):
            response.status_code = status
        return mapping
    return result


def _require_dependency[T](value: T | None, label: str) -> T:
    """Fail closed when composition omitted a required route dependency."""

    if value is None:
        del label
        raise ConfigurationProblem(
            "CONFIGURATION_INVALID",
            "A required application dependency is unavailable.",
            status_code=503,
        )
    return value


def _resolve_review_candidate(payload: object, candidate_handle: str) -> dict[str, object] | None:
    queue = mapping(payload)
    for item in required_list(queue, "candidates"):
        row = mapping(item)
        raw_handle = row.get("handle")
        projected = (
            raw_handle
            if isinstance(raw_handle, str) and raw_handle == candidate_handle
            else opaque_navigation_handle(raw_handle, "candidate")
            if isinstance(raw_handle, str)
            else None
        )
        if projected == candidate_handle:
            return row
    return None



async def _manual_capture_snapshot(
    client: SemanticCoreClient,
    context: TrustedRequestContext,
    candidate_handle: str,
    *,
    missing_is_none: bool,
) -> VerifiedManualCapture | None:
    """Read Core's same-project Note and re-verify its source version and Unicode span."""

    try:
        raw = await client.request(
            context,
            "GET",
            f"/v1/projects/{context.project_id}/candidates/{candidate_handle}/source-context",
        )
    except SemanticCoreProblem as error:
        if missing_is_none and error.status_code == 404:
            return None
        raise
    if not isinstance(raw, dict):
        raise SemanticCoreProblem(
            503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid manual source context"
        )
    payload = {key: value for key, value in raw.items() if key != "_projecta_http_status"}
    try:
        return resolve_manual_capture(context.project_id, payload)
    except ManualCaptureContextError as error:
        raise SemanticCoreProblem(
            409, "MANUAL_CAPTURE_INVALID", "The manual Note source anchor is invalid or stale"
        ) from error


def _manual_capture_review_fields(
    project_id: str,
    raw_handle: object,
    capture: VerifiedManualCapture,
) -> dict[str, object]:
    """Adapt verified manual source context to the existing source-first review contract."""

    if not isinstance(raw_handle, str) or not raw_handle:
        raise SemanticCoreProblem(
            503, "SEMANTIC_CONTRACT_UNAVAILABLE", "The manual candidate identity is unavailable"
        )
    source = capture.source_version
    anchor = capture.anchor
    return {
        "candidateRevision": capture.candidate_revision,
        "label": capture.evidence_text,
        "proposedType": capture.entity_type,
        "constrainedContractVersion": "manual-entity-capture.v1",

        "sourceText": capture.source_text,
        "sourceVersion": {
            "revision": 1,
            "sourceVersionId": source.source_version_id,
            "canonicalizationVersion": source.canonicalization_version,
            "coordinateSystemVersion": source.coordinate_system_version,
            "originalDigest": source.original_content_digest,
            "canonicalDigest": source.canonical_content_digest,
        },
        "evidence": {
            "status": "selected",
            "digest": anchor.quote_digest,
            "highlights": [
                {
                    "kind": "evidence",
                    "startOffset": anchor.start_offset,
                    "endOffset": anchor.end_offset,
                    "originalByteStart": anchor.original_start_byte,
                    "originalByteEnd": anchor.original_end_byte,
                    "utf16Start": anchor.utf16_start_offset,
                    "utf16End": anchor.utf16_end_offset,
                    "quote": anchor.exact_quote,
                    "quoteDigest": anchor.quote_digest,
                }
            ],
        },
        "manualCapture": {
            "mode": "human-authored-zero-model",
            "entityHandle": _review_receipt_handle(project_id, raw_handle),
        },
    }


def _review_receipt_handle(project_id: str, raw_handle: str) -> str:
    """Derive a project-scoped server-owned entity handle without exposing Core IDs."""

    digest = sha256(f"{project_id}:review-entity:{raw_handle}".encode()).hexdigest()
    return f"eh1_{digest}"


def _manual_capture_receipt_request(
    project_id: str,
    candidate_handle: str,
    capture: VerifiedManualCapture,
    idempotency_key: str,
    decision: Literal["confirm", "reject", "abstain"],
    decision_payload_digest: str | None,
) -> ReviewDecisionRequest:
    """Bind an RM-61 decision to the server-resolved manual Note source anchor."""

    return ReviewDecisionRequest(
        projectId=project_id,
        itemKind="entity",
        itemHandle=_review_receipt_handle(project_id, candidate_handle),
        candidateRevision=capture.candidate_revision,
        expectedCandidateRevision=0,
        sourceVersionId=capture.source_version.source_version_id,
        sourceVersionRevision=1,
        constrainedContractVersion="manual-entity-capture.v1",
        evidenceDigest=capture.anchor.quote_digest,
        previousDecisionDigest=None,
        idempotencyKey=idempotency_key,
        decision=decision,
        decisionPayloadDigest=decision_payload_digest,
    )


def _latest_review_receipt(
    extraction: ExtractionService | None,
    context: TrustedRequestContext,
    raw_handle: object,
) -> dict[str, object] | None:
    if extraction is None or not isinstance(raw_handle, str) or not raw_handle:
        return None
    actor = ReviewActorContext(
        project_id=context.project_id,
        actor_id=context.actor_id,
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )
    try:
        history = extraction.review_decision_history(
            context, actor, "entity", _review_receipt_handle(context.project_id, raw_handle)
        )
    except (RuntimeError, ValueError):
        return None
    if not history:
        return None
    latest = max(history, key=lambda item: item.sequence)
    state = (
        "abstained"
        if latest.decision == "abstain"
        else "rejected"
        if latest.decision == "reject"
        else "accepted"
    )
    return {
        "state": state,
        "receiptDigest": latest.receipt_digest,
        "candidateRevision": latest.candidate_revision,
        "sourceVersionRevision": latest.source_version_revision,
    }

def _require_local_suggestion_service(
    service: LocalSuggestionService | None,
) -> LocalSuggestionService:
    if service is None:
        raise SemanticCoreProblem(
            503, "LOCAL_SUGGESTION_UNAVAILABLE", "Local suggestion storage is unavailable"
        )
    return service


def _local_suggestion_problem(error: LocalSuggestionError) -> SemanticCoreProblem:
    problems: dict[str, tuple[int, str, str]] = {
        "production_disabled": (
            404,
            "LOCAL_SUGGESTION_DISABLED",
            "Local suggestions are disabled in this runtime.",
        ),
        "local_model_not_configured": (
            503,
            "LOCAL_MODEL_NOT_CONFIGURED",
            "Configure a local model before requesting a suggestion.",
        ),
        "local_runtime_unavailable": (
            503,
            "LOCAL_MODEL_UNAVAILABLE",
            "The configured local model runtime is unavailable.",
        ),
        "local_output_invalid": (
            502,
            "LOCAL_SUGGESTION_INVALID",
            "The local model returned an unsupported proposal.",
        ),
        "source_too_large": (
            413,
            "LOCAL_SUGGESTION_SOURCE_TOO_LARGE",
            "This Note is too large for one bounded local suggestion.",
        ),
    }
    status, code, detail = problems.get(
        error.code,
        (503, "LOCAL_SUGGESTION_UNAVAILABLE", "The local suggestion operation failed safely."),
    )
    return SemanticCoreProblem(status, code, detail)


async def _local_suggestion_subject(
    client: SemanticCoreClient,
    extraction: ExtractionService | None,
    context: TrustedRequestContext,
    candidate_handle: str,
) -> tuple[LocalSuggestionSubject, list[LocalSuggestionLinkOption]]:
    extraction_service = _require_dependency(extraction, "review receipt persistence")
    capture = await _manual_capture_snapshot(
        client, context, candidate_handle, missing_is_none=False
    )
    if capture is None:
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The manual candidate is not visible")
    if capture.candidate_status != "validated":
        raise SemanticCoreProblem(
            409, "LOCAL_SUGGESTION_REQUIRES_VALIDATION", "Validate the manual occurrence first"
        )
    _require_confirmed_manual_capture(
        extraction_service, context, candidate_handle, capture
    )

    targets = await client.entity_link_context(context, limit=MAX_LINK_TARGETS)
    link_options: list[LocalSuggestionLinkOption] = []
    suggestion_targets: list[LocalSuggestionTarget] = []
    seen_handles: set[str] = set()
    for target in targets:
        raw_id = target.get("id")
        raw_label = target.get("label")
        if not isinstance(raw_id, str) or not raw_id or not isinstance(raw_label, str):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Same-project link context is invalid"
            )
        label = raw_label.strip()
        if not label or len(label) > 256:
            continue
        handle = opaque_navigation_handle(raw_id, "entity")
        if handle in seen_handles:
            continue
        seen_handles.add(handle)
        link_options.append(LocalSuggestionLinkOption(handle=handle, label=label))
        suggestion_targets.append(LocalSuggestionTarget(handle=handle, label=label))

    key = _manual_capture_workflow_key(context, candidate_handle, capture)
    subject = LocalSuggestionSubject(
        key=key,
        title=capture.title,
        source_text=capture.source_text,
        confirmed_quote=capture.evidence_text,
        confirmed_type=capture.entity_type,
        link_targets=tuple(suggestion_targets),
    )
    return subject, link_options


def _manual_capture_workflow_key(
    context: TrustedRequestContext,
    candidate_handle: str,
    capture: VerifiedManualCapture,
) -> LocalSuggestionKey:
    return LocalSuggestionKey(
        project_id=context.project_id,
        source_version_id=capture.source_version.source_version_id,
        source_version_revision=1,
        item_handle=candidate_handle,
        item_revision=capture.candidate_revision,
        evidence_digest=capture.anchor.quote_digest,
    )


def _manual_edit_telemetry(
    payload: StructuredCandidateEditRequest,
) -> tuple[tuple[CorrectionDimension, ...], int, bool]:
    dimensions: list[CorrectionDimension] = []
    if payload.entity_type is not None:
        dimensions.append("type")
    if payload.label is not None:
        dimensions.append("label")
    if payload.relation is not None:
        dimensions.append("predicate")
    if payload.entity_link is not None or payload.assignment is not None:
        dimensions.append("endpoint")
    semantic_edit_count = sum(
        value is not None
        for value in (
            payload.entity_type,
            payload.label,
            payload.relation,
            payload.entity_link,
            payload.date,
            payload.assignment,
        )
    )
    # Date adds no dimension and does not suppress other correction dimensions.
    return tuple(dimensions), semantic_edit_count, not dimensions


async def _controlled_relation_endpoint(
    client: SemanticCoreClient,
    extraction: ExtractionService,
    context: TrustedRequestContext,
    candidate_handle: str,
) -> ControlledRelationEndpoint:
    capture = await _manual_capture_snapshot(
        client, context, candidate_handle, missing_is_none=False
    )
    if capture is None:
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The relation endpoint is not visible")
    return _controlled_relation_endpoint_from_capture(
        extraction, context, candidate_handle, capture
    )


def _controlled_relation_endpoint_from_capture(
    extraction: ExtractionService,
    context: TrustedRequestContext,
    candidate_handle: str,
    capture: VerifiedManualCapture,
) -> ControlledRelationEndpoint:
    if capture.candidate_status != "validated":
        raise SemanticCoreProblem(
            409,
            "CONTROLLED_RELATION_REQUIRES_VALIDATION",
            "Validate both manual occurrences before relating them.",
        )
    try:
        confirmation = _require_confirmed_manual_capture(
            extraction, context, candidate_handle, capture
        )
    except SemanticCoreProblem as error:
        if error.code == "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION":
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_REQUIRES_CONFIRMATION",
                "Confirm both manual occurrences before relating them.",
            ) from error
        raise
    return ControlledRelationEndpoint(
        candidate_handle=candidate_handle,
        entity_handle=_review_receipt_handle(context.project_id, candidate_handle),
        capture=capture,
        confirmation=confirmation,
    )


async def _controlled_relation_subject(
    client: SemanticCoreClient,
    extraction: ExtractionService | None,
    context: TrustedRequestContext,
    selected_candidate_handle: str,
    target_candidate_handle: str,
    direction: RelationDirection,
    mode: RelationSuggestionMode,
    predicate: str | None,
) -> tuple[LocalSuggestionSubject, list[LocalSuggestionLinkOption]]:
    if selected_candidate_handle == target_candidate_handle:
        raise SemanticCoreProblem(
            422, "CONTROLLED_RELATION_INVALID_PAIR", "Relation endpoints must be distinct."
        )
    extraction_service = _require_dependency(extraction, "review receipt persistence")
    selected = await _controlled_relation_endpoint(
        client, extraction_service, context, selected_candidate_handle
    )
    target = await _controlled_relation_endpoint(
        client, extraction_service, context, target_candidate_handle
    )
    try:
        relation = build_relation_suggestion_context(
            context.project_id, selected, target, direction
        )
    except ValueError as error:
        code = (
            "CONTROLLED_RELATION_STALE"
            if "share one current source version" in str(error)
            else "CONTROLLED_RELATION_INVALID_PAIR"
        )
        raise SemanticCoreProblem(
            409,
            code,
            "The selected endpoints do not have one current, shared source context.",
        ) from error
    workflow_item = relation_workflow_item_handle(
        selected_candidate_handle,
        target_candidate_handle,
        direction,
        mode,
        predicate if mode == "manual" else None,
    )
    key = LocalSuggestionKey(
        project_id=context.project_id,
        source_version_id=selected.capture.source_version.source_version_id,
        source_version_revision=1,
        item_handle=workflow_item,
        item_revision=selected.capture.candidate_revision,
        evidence_digest=relation.evidence_digest,
    )
    subject = LocalSuggestionSubject(
        key=key,
        title=selected.capture.title,
        source_text=selected.capture.source_text,
        confirmed_quote=selected.capture.evidence_text,
        confirmed_type=selected.capture.entity_type,
        link_targets=(),
        relation_context=relation,
    )
    return subject, []


def _controlled_relation_proposal(
    context: RelationSuggestionContext,
    option: RelationSuggestionOption,
    mode: RelationSuggestionMode,
) -> LocalSuggestionProposal:
    return LocalSuggestionProposal(
        kind="relation",
        targetHandle=option.target_handle,
        relationId=option.relation_id,
        sourceHandle=option.source_handle,
        selectedCandidateHandle=context.selected_candidate_handle,
        targetCandidateHandle=context.target_candidate_handle,
        sourceCandidateHandle=option.source_candidate_handle,
        semanticTargetCandidateHandle=option.target_candidate_handle,
        predicate=option.predicate,
        direction=option.direction,
        relationEvidenceDigest=option.evidence_digest,
        relationMode=mode,
        relationEvidence=option.evidence,
    )


async def _controlled_relation_state(
    client: SemanticCoreClient,
    extraction: ExtractionService | None,
    service: LocalSuggestionService,
    context: TrustedRequestContext,
    candidate_handle: str,
    suggestion_id: str,
) -> tuple[LocalSuggestionResponse, LocalSuggestionSubject, LocalSuggestionProposal]:
    if len(suggestion_id) != 68 or not suggestion_id.startswith("ls1_"):
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The relation suggestion is not visible")
    stored = service.stored_suggestion(suggestion_id, context.project_id)
    if stored is None or stored.proposal_json is None:
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The relation suggestion is not visible")
    try:
        proposal = LocalSuggestionProposal.model_validate_json(stored.proposal_json)
    except ValueError as error:
        raise SemanticCoreProblem(
            409, "CONTROLLED_RELATION_STALE", "The stored relation suggestion is invalid."
        ) from error
    if proposal.kind not in {"relation", "abstain"}:
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The relation suggestion is not visible")
    if (
        proposal.selected_candidate_handle != candidate_handle
        or proposal.target_candidate_handle is None
        or proposal.direction is None
        or proposal.relation_mode is None
    ):
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The relation suggestion is not visible")
    if proposal.kind == "relation" and (
        proposal.relation_id is None
        or proposal.predicate is None
        or proposal.relation_evidence_digest is None
    ):
        raise SemanticCoreProblem(
            409, "CONTROLLED_RELATION_STALE", "The stored relation suggestion is incomplete."
        )
    if proposal.kind == "abstain" and (
        proposal.relation_mode != "local" or proposal.predicate is not None
    ):
        raise SemanticCoreProblem(
            409, "CONTROLLED_RELATION_STALE", "The stored relation abstention is invalid."
        )
    subject, link_options = await _controlled_relation_subject(
        client,
        extraction,
        context,
        candidate_handle,
        proposal.target_candidate_handle,
        proposal.direction,
        proposal.relation_mode,
        proposal.predicate if proposal.relation_mode == "manual" else None,
    )
    relation = subject.relation_context
    if relation is None or subject.key.workflow_id != suggestion_id:
        raise SemanticCoreProblem(
            409,
            "CONTROLLED_RELATION_STALE",
            "The relation endpoints, confirmation receipts, or source anchor have changed.",
        )
    if proposal.kind == "relation":
        option = relation.option_for(proposal.predicate or "")
        if (
            option is None
            or option.relation_id != proposal.relation_id
            or option.evidence_digest != proposal.relation_evidence_digest
            or option.source_handle != proposal.source_handle
            or option.target_handle != proposal.target_handle
            or option.source_candidate_handle != proposal.source_candidate_handle
            or option.target_candidate_handle != proposal.semantic_target_candidate_handle
        ):
            raise SemanticCoreProblem(
                409,
                "CONTROLLED_RELATION_STALE",
                "The relation evidence or confirmed endpoint has changed.",
            )
    current = service.read(subject.key, context.actor_id, link_options)
    if current.suggestion is None or current.suggestion.suggestion_id != suggestion_id:
        raise SemanticCoreProblem(404, "RESOURCE_NOT_FOUND", "The relation suggestion is not visible")
    return current, subject, proposal




def _require_confirmed_manual_capture(
    extraction: ExtractionService,
    context: TrustedRequestContext,
    candidate_handle: str,
    capture: VerifiedManualCapture,
) -> ReviewDecisionReceiptRecord:
    actor = _local_suggestion_actor(context)
    try:
        history = extraction.review_decision_history(
            context,
            actor,
            "entity",
            _review_receipt_handle(context.project_id, candidate_handle),
        )
    except (RuntimeError, ValueError) as error:
        raise SemanticCoreProblem(
            503, "REVIEW_RECEIPTS_UNAVAILABLE", "The manual confirmation receipt is unavailable"
        ) from error
    if not history:
        raise SemanticCoreProblem(
            409,
            "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION",
            "Confirm this occurrence before requesting a local suggestion.",
        )
    latest = max(history, key=lambda item: item.sequence)
    source_digest = "sha256:" + sha256(
        capture.source_version.source_version_id.encode("utf-8", "strict")
    ).hexdigest()
    if (
        latest.decision != "confirm"
        or latest.candidate_revision != capture.candidate_revision
        or latest.source_version_digest != source_digest
        or latest.source_version_revision != 1
        or latest.constrained_contract_version != "manual-entity-capture.v1"
        or latest.evidence_digest != capture.anchor.quote_digest
    ):
        raise SemanticCoreProblem(
            409,
            "LOCAL_SUGGESTION_REQUIRES_CONFIRMATION",
            "A current confirmation receipt for this occurrence is required.",
        )
    return latest


def _local_suggestion_actor(context: TrustedRequestContext) -> ReviewActorContext:
    return ReviewActorContext(
        project_id=context.project_id,
        actor_id=context.actor_id,
        capability="candidate.review",
        authorization_revision="trusted-context.v1",
    )


def _local_suggestion_receipt_handle(project_id: str, suggestion_id: str) -> str:
    return _review_receipt_handle(project_id, f"local-suggestion:{suggestion_id}")


def _local_suggestion_receipt_request(
    context: TrustedRequestContext,
    subject: LocalSuggestionSubject,
    receipt_handle: str,
    idempotency_key: str,
    decision: Literal["confirm", "edit", "reject"],
    decision_digest: str,
    receipt_revision: int,
    previous_decision_digest: str | None,
) -> ReviewDecisionRequest:
    return ReviewDecisionRequest(
        projectId=context.project_id,
        itemKind="entity",
        itemHandle=receipt_handle,
        candidateRevision=receipt_revision,
        expectedCandidateRevision=receipt_revision - 1,
        sourceVersionId=subject.key.source_version_id,
        sourceVersionRevision=subject.key.source_version_revision,
        constrainedContractVersion="local-suggestion.v1",
        evidenceDigest=subject.key.evidence_digest,
        previousDecisionDigest=previous_decision_digest,
        idempotencyKey=idempotency_key,
        decision=decision,
        decisionPayloadDigest=decision_digest,
    )


def _local_suggestion_decision_digest(payload: LocalSuggestionDecisionRequest) -> str:
    body = json.dumps(
        payload.model_dump(mode="json", by_alias=True, exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + sha256(body.encode("utf-8", "strict")).hexdigest()

def _controlled_relation_decision_digest(
    payload: ControlledRelationDecisionRequest,
) -> str:
    body = json.dumps(
        payload.model_dump(mode="json", by_alias=True, exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + sha256(body.encode("utf-8", "strict")).hexdigest()


def _controlled_relation_receipt_request(
    context: TrustedRequestContext,
    key: LocalSuggestionKey,
    relation_id: str,
    evidence_digest: str,
    idempotency_key: str,
    decision: Literal["confirm", "reject"],
    decision_digest: str,
    candidate_revision: int,
    expected_candidate_revision: int,
    previous_decision_digest: str | None,
) -> ReviewDecisionRequest:
    return ReviewDecisionRequest(
        projectId=context.project_id,
        itemKind="relation",
        itemHandle=relation_id,
        candidateRevision=candidate_revision,
        expectedCandidateRevision=expected_candidate_revision,
        sourceVersionId=key.source_version_id,
        sourceVersionRevision=key.source_version_revision,
        constrainedContractVersion="controlled-relation-suggestion.v1",
        evidenceDigest=evidence_digest,
        previousDecisionDigest=previous_decision_digest,
        idempotencyKey=idempotency_key,
        decision=decision,
        decisionPayloadDigest=decision_digest,
    )




def _require_selected_project_handle(request: Request, handle: str) -> None:
    if request.headers.get("X-Projecta-Selection-Handle") != handle:
        raise _project_not_found()
    try:
        require_opaque_handle(handle, ("project",))
    except ValueError as error:
        raise SemanticCoreProblem(
            400, "INVALID_PROJECT_HANDLE", "The project handle is invalid"
        ) from error


def _note_draft_store(request: Request) -> StructuredNoteDraftStore:
    store = getattr(request.app.state, "structured_note_draft_store", None)
    if not isinstance(store, StructuredNoteDraftStore):
        raise ConfigurationProblem(
            "CONFIGURATION_INVALID", "Structured Note draft storage is unavailable", status_code=503
        )
    return store


def _draft_response(
    request_id: str, stored: StoredStructuredNoteDraft, replayed: bool
) -> StructuredNoteDraftResponse:
    canonical = canonicalize_structured_note(stored.draft)
    committed = stored.committed_note_id
    return StructuredNoteDraftResponse(
        **canonical.model_dump(mode="json", by_alias=True),
        requestId=request_id,
        draftHandle=stored.handle,
        revision=stored.revision,
        committedNoteHandle=(opaque_navigation_handle(committed, "note") if committed else None),
        replayed=replayed,
    )


def _map_note_list(raw: object) -> list[StructuredNoteListItem]:
    payload = mapping(raw)
    notes = required_list(payload, "notes")
    result: list[StructuredNoteListItem] = []
    for value in notes:
        if not isinstance(value, dict):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note list"
            )
        typed_value = cast(dict[str, object], value)
        raw_types = required_list(typed_value, "itemTypeSummary")
        if any(not isinstance(item, str) for item in raw_types):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note list"
            )
        types = cast(list[NoteItemType], raw_types)
        result.append(
            StructuredNoteListItem(
                handle=_required_string(typed_value, "noteHandle"),
                title=_required_string(typed_value, "title"),
                author=_required_string(typed_value, "author"),
                recordedAt=_required_string(typed_value, "recordedAt"),
                itemTypeSummary=types,
                candidateState=_required_string(typed_value, "candidateState"),
                evidenceCoverage=_required_float(typed_value, "evidenceCoverage"),
            )
        )
    return result


def _map_note_detail(raw: object, request_id: str) -> StructuredNoteDetailResponse:
    """Validate a source Note projection without rewriting source text."""
    if not isinstance(raw, dict):
        raise SemanticCoreProblem(
            503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note detail"
        )
    typed = cast(dict[str, object], raw)
    raw_items = typed.get("items", [])
    if not isinstance(raw_items, list):
        raise SemanticCoreProblem(
            503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note detail"
        )
    items: list[dict[str, object]] = []
    for item in cast(list[object], raw_items):
        if not isinstance(item, dict):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note detail"
            )
        value = cast(dict[str, object], item)
        if not all(isinstance(value.get(field), str) for field in ("itemType", "content")):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note detail"
            )
        if not all(isinstance(value.get(field), int) for field in ("startOffset", "endOffset")):
            raise SemanticCoreProblem(
                503, "SEMANTIC_CONTRACT_UNAVAILABLE", "Semantic Core returned invalid Note detail"
            )
        items.append(value)
    return StructuredNoteDetailResponse(
        requestId=request_id,
        noteHandle=_required_string(typed, "noteHandle"),
        title=_required_string(typed, "title"),
        rawText=_required_string(typed, "rawText"),
        author=_required_string(typed, "author"),
        recordedAt=_required_string(typed, "recordedAt"),
        items=[StructuredNoteItemProjection.model_validate(item) for item in items],
        evidenceCoverage=_required_float(typed, "evidenceCoverage"),
        candidateState=_required_string(typed, "candidateState"),
    )


def _note_item_proposals(extracted: ExtractionResponse) -> list[StructuredNoteItemDraft]:
    type_map: dict[str, NoteItemType] = {
        "Requirement": "requirement",
        "Decision": "decision",
        "Question": "question",
        "Task": "task",
        "Risk": "risk",
        "Assumption": "assumption",
        "Constraint": "constraint",
        "ProgressClaim": "progress-update",
        "ResearchFinding": "research-need",
    }
    ordered = sorted(
        extracted.entities,
        key=lambda entity: (entity.evidence.start_offset, entity.evidence.end_offset),
    )
    return [
        StructuredNoteItemDraft(
            itemType=type_map[entity.type],
            content=entity.evidence.text,
        )
        for entity in ordered
    ]


def _apply_candidate_correction(
    confirmation: ConfirmationRequest, edit: StoredCandidateEdit | None
) -> ConfirmationRequest:
    current_revision = edit.revision if edit is not None else 0
    if confirmation.correction_revision != current_revision:
        raise SemanticCoreProblem(
            409,
            "CANDIDATE_EDIT_CONFLICT",
            "The candidate correction changed after validation",
        )
    if edit is None:
        return confirmation
    correction = edit.payload
    if correction.entity_type is not None and correction.entity_type != "Requirement":
        raise SemanticCoreProblem(
            422,
            "CANDIDATE_TYPE_NOT_CONFIRMABLE",
            "The released confirmation contract supports Requirement candidates only",
        )
    assertion = confirmation.assertion.model_copy(
        update={
            "label": correction.label or confirmation.assertion.label,
            "valid_from": correction.date or confirmation.assertion.valid_from,
        }
    )
    return confirmation.model_copy(update={"assertion": assertion})


def _validate_handle(handle: str, kinds: tuple[str, ...]) -> None:
    try:
        require_opaque_handle(handle, kinds)
    except ValueError as error:
        raise SemanticCoreProblem(
            400, "INVALID_NAVIGATION_HANDLE", "The navigation handle is invalid"
        ) from error


def _csv(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return []
    values = [item.strip() for item in value.split(",") if item.strip()]
    if len(values) > 20:
        raise SemanticCoreProblem(400, "INVALID_GRAPH_FILTER", "Too many graph filters")
    return list(dict.fromkeys(values))


def _graph_filters(
    semantic_types: str | None,
    verification_states: str | None,
    lifecycle_states: str | None,
    provenance_states: str | None,
    relation_types: str | None,
    evidence: str,
) -> dict[str, str | None]:
    try:
        node_types = finite_types(_csv(semantic_types), NODE_TYPES, "semantic type")
        relations = finite_types(_csv(relation_types), RELATION_TYPES, "relation type")
    except ValueError as error:
        raise SemanticCoreProblem(400, "INVALID_GRAPH_FILTER", str(error)) from error
    verification = _csv(verification_states)
    lifecycle = _csv(lifecycle_states)
    provenance = _csv(provenance_states)
    allowed_verification = {"candidate", "asserted", "inferred", "unverified"}
    allowed_lifecycle = {
        "current",
        "pending-review",
        "confirmed",
        "rejected",
        "superseded",
        "retracted",
        "stale",
    }
    allowed_provenance = {"source-backed", "human-confirmed", "rule-derived", "candidate-proposed"}
    if any(item not in allowed_verification for item in verification):
        raise SemanticCoreProblem(
            400, "INVALID_GRAPH_FILTER", "verification state is not allowlisted"
        )
    if any(item not in allowed_lifecycle for item in lifecycle):
        raise SemanticCoreProblem(400, "INVALID_GRAPH_FILTER", "lifecycle state is not allowlisted")
    if any(item not in allowed_provenance for item in provenance):
        raise SemanticCoreProblem(
            400, "INVALID_GRAPH_FILTER", "provenance state is not allowlisted"
        )
    return {
        "semanticTypes": ",".join(node_types) or None,
        "verificationStates": ",".join(verification) or None,
        "lifecycleStates": ",".join(lifecycle) or None,
        "provenanceStates": ",".join(provenance) or None,
        "relationTypes": ",".join(relations) or None,
        "evidence": evidence,
    }


def _core_query_path(path: str, params: dict[str, object]) -> str:
    filtered = {key: str(value) for key, value in params.items() if value is not None}
    return f"{path}?{urlencode(filtered)}" if filtered else path


def _required_string(row: dict[str, object], field: str) -> str:
    value = required(row, field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"response field is not a non-empty string: {field}")
    return value


def _required_float(row: dict[str, object], field: str) -> float:
    value = required(row, field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"response field is not numeric: {field}")
    return float(value)


def _id_free_payload(raw: object, request_id: str, project_handle: str, item_handle: str) -> object:
    """Allow only display-safe values from a typed Core detail response."""

    def clean(value: object, key: str = "") -> object:
        if isinstance(value, dict):
            result: dict[str, object] = {}
            typed_value = cast(dict[object, object], value)
            for raw_key, raw_value in typed_value.items():
                if not isinstance(raw_key, str):
                    raise ValueError("Core response contains a non-string object key")
                if raw_key in {
                    "projectId",
                    "candidateId",
                    "itemId",
                    "assertedItemId",
                    "sourceId",
                    "graphName",
                    "graphIri",
                }:
                    continue
                result[raw_key] = clean(raw_value, raw_key)
            return result
        if isinstance(value, list):
            return [clean(item, key) for item in cast(list[object], value)]
        if isinstance(value, str) and "://" in value:
            return "resource-h-" + sha256(value.encode("utf-8")).hexdigest()[:24]
        return value

    cleaned = clean(mapping(raw))
    if not isinstance(cleaned, dict):
        raise ValueError("Core response must be an object")
    typed_cleaned = cast(dict[str, object], cleaned)
    typed_cleaned.pop("_projecta_http_status", None)
    typed_cleaned["requestId"] = request_id
    typed_cleaned["projectHandle"] = project_handle
    typed_cleaned["handle"] = item_handle
    return typed_cleaned
