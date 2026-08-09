"""HTTP routes for typed capture, review, and finite read operations."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Protocol, cast
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from projecta_api.configuration.audit import ConfigurationAudit
from projecta_api.configuration.connection import ProviderConnectionChecker
from projecta_api.configuration.errors import ConfigurationProblem
from projecta_api.configuration.models import (
    LLMProfileRemove,
    LLMProfileWrite,
)
from projecta_api.configuration.ports import RuntimeConfigurationProvider
from projecta_api.configuration.service import LLMConfigurationService
from projecta_api.context import (
    TrustedActorContext,
    TrustedRequestContext,
    trusted_actor_context,
    trusted_context,
)
from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.graph_projection import (
    NODE_TYPES,
    RELATION_TYPES,
    CandidateQueueResponse,
    GraphEvidenceResponse,
    GraphLifecycleResponse,
    GraphNodeDetail,
    GraphProjectionResponse,
    KnowledgeCollectionResponse,
    finite_types,
    mapping,
    opaque_navigation_handle,
    project_candidate_queue,
    project_graph_page,
    project_knowledge_collection,
    project_link_response,
    project_node_detail,
    require_opaque_handle,
    required,
    required_list,
)
from projecta_api.models import (
    CaptureRequest,
    CaptureResponse,
    ConfirmationRequest,
    ExtractionRequest,
    RejectionRequest,
    TypedSegment,
)
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


class ExtractionService(Protocol):
    async def extract(
        self, context: TrustedRequestContext, key: str, request: ExtractionRequest
    ) -> object: ...

    async def propose(
        self, context: TrustedRequestContext, request: ExtractionRequest
    ) -> ExtractionResponse: ...


def create_router(
    client: SemanticCoreClient,
    extraction: ExtractionService | None = None,
    retrieval: RetrievalService | None = None,
    configuration_service: LLMConfigurationService | None = None,
    runtime_configuration: RuntimeConfigurationProvider | None = None,
    connection_checker: ProviderConnectionChecker | None = None,
    configuration_audit: ConfigurationAudit | None = None,
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
        response.headers["X-Request-Id"] = context.request_id
        return ProjectOverviewResponse.model_validate(mapped)

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
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
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

    @router.post("/v1/projects/{handle}/candidates/{candidate_handle}/validations")
    async def validate_selected_candidate(
        handle: str,
        candidate_handle: str,
        context: Context,
        request: Request,
        response: Response,
    ) -> object:
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
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
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
        _require_selected_project_handle(request, handle)
        _validate_handle(candidate_handle, ("candidate", "node"))
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
            payload.model_dump(mode="json", by_alias=True),
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
