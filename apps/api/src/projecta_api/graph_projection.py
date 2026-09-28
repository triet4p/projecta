"""Strict, finite graph and knowledge projections for the project workspace.

The browser receives labels and revision-bound opaque handles only.  This module
is deliberately independent from RDF, graph names, and Semantic Core storage
identifiers so that the public boundary cannot accidentally become an RDF
browser.
"""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

ProjectionVersion = Literal["s8.graph.v1"]
Direction = Literal["source-to-target", "target-to-source"]
VerificationState = Literal["candidate", "asserted", "inferred", "unverified"]
LifecycleState = Literal[
    "current",
    "pending-review",
    "confirmed",
    "rejected",
    "superseded",
    "retracted",
    "stale",
]
ProvenanceState = Literal["source-backed", "human-confirmed", "rule-derived", "candidate-proposed"]
EvidenceFilter = Literal["any", "with-evidence", "without-evidence"]
EvidenceState = Literal["available", "unavailable", "stale"]
ReviewAnchorKind = Literal["endpoint", "trigger", "evidence"]
ReviewEvidenceStatus = Literal["selected", "review-required", "abstained", "quarantined", "unavailable"]
ReviewReceiptStatus = Literal[
    "not-recorded", "accepted", "rejected", "abstained", "stale", "quarantined"
]

NODE_TYPES = (
    "Project",
    "Note",
    "NoteItem",
    "Requirement",
    "Decision",
    "Question",
    "Task",
    "Risk",
    "Assumption",
    "Constraint",
    "ProgressClaim",
    "ResearchFinding",
    "Person",
    "Candidate",
    "SourceArtifact",
)
RELATION_TYPES = (
    "implements",
    "blocks",
    "dependsOn",
    "supports",
    "answers",
    "resolves",
    "constrainedBy",
    "supersedes",
    "derivedFrom",
    "hasNoteItem",
    "belongsToProject",
    "evidenceFor",
    "provenanceFor",
)


class ProjectionDates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_from: date | None = Field(default=None, alias="validFrom")
    valid_to: date | None = Field(default=None, alias="validTo")
    recorded_at: datetime | None = Field(default=None, alias="recordedAt")


class GraphFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic_types: list[str] = Field(alias="semanticTypes")
    verification_states: list[VerificationState] = Field(alias="verificationStates")
    lifecycle_states: list[LifecycleState] = Field(alias="lifecycleStates")
    provenance_states: list[ProvenanceState] = Field(alias="provenanceStates")
    relation_types: list[str] = Field(alias="relationTypes")
    evidence: EvidenceFilter


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str
    label: str = Field(min_length=1, max_length=500)
    semantic_type: str = Field(alias="semanticType")
    lifecycle_state: LifecycleState = Field(alias="lifecycleState")
    verification_state: VerificationState = Field(alias="verificationState")
    provenance_state: ProvenanceState = Field(alias="provenanceState")
    direction: Direction | None = None
    evidence_count: int = Field(ge=0, alias="evidenceCount")
    project_scope: Literal["selected"] = Field(alias="projectScope")
    dates: ProjectionDates
    available_actions: list[str] = Field(alias="availableActions")


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str
    source_handle: str = Field(alias="sourceHandle")
    target_handle: str = Field(alias="targetHandle")
    relation_type: str = Field(alias="relationType")
    direction: Direction
    verification_state: VerificationState = Field(alias="verificationState")
    provenance_state: ProvenanceState = Field(alias="provenanceState")
    evidence_count: int = Field(ge=0, alias="evidenceCount")


class GraphPageInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_limit: int = Field(alias="nodeLimit", ge=1, le=100)
    edge_limit: int = Field(alias="edgeLimit", ge=1, le=200)
    has_more: bool = Field(alias="hasMore")
    continuation: str | None = None
    expansion_available: bool = Field(alias="expansionAvailable")


class GraphProjectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_version: ProjectionVersion = Field(alias="projectionVersion")
    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    source_revision: str = Field(alias="sourceRevision")
    materialization_revision: str = Field(alias="materializationRevision")
    as_of: datetime = Field(alias="asOf")
    stale: bool
    partial: bool
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    page: GraphPageInfo
    filters: GraphFilters


class GraphRelationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: str = Field(alias="relationType")
    direction: Direction
    peer_handle: str = Field(alias="peerHandle")
    peer_label: str = Field(alias="peerLabel")


class GraphNodeDetail(GraphNode):
    project_label: str = Field(alias="projectLabel")
    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    summary: str | None = None
    source_summary: str | None = Field(default=None, alias="sourceSummary")
    freshness: EvidenceState
    relations: list[GraphRelationSummary]
    evidence: list[str]
    lifecycle: list[str]


class GraphEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_version: ProjectionVersion = Field(alias="projectionVersion")
    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    node_handle: str = Field(alias="nodeHandle")
    stale: bool
    items: list[dict[str, str | int | None]]


class GraphLifecycleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_version: ProjectionVersion = Field(alias="projectionVersion")
    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    node_handle: str = Field(alias="nodeHandle")
    stale: bool
    items: list[dict[str, str | None]]


class CandidateQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str
    label: str = Field(min_length=1, max_length=500)
    source_excerpt: str | None = Field(default=None, alias="sourceExcerpt")
    proposed_type: str = Field(alias="proposedType")
    proposed_relations: list[str] = Field(alias="proposedRelations")
    validation_state: str = Field(alias="validationState")
    confidence: float | None = Field(default=None, ge=0, le=1)
    age: str | None = None
    lifecycle_state: LifecycleState = Field(alias="lifecycleState")
    evidence_count: int = Field(ge=0, alias="evidenceCount")


class CandidateQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    source_revision: str = Field(alias="sourceRevision")
    stale: bool
    candidates: list[CandidateQueueItem]
    has_more: bool = Field(alias="hasMore")


class ReviewSourceVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    source_version_id: str | None = Field(default=None, alias="sourceVersionId")
    canonicalization_version: str | None = Field(default=None, alias="canonicalizationVersion")
    coordinate_system_version: str | None = Field(default=None, alias="coordinateSystemVersion")
    original_digest: str | None = Field(default=None, alias="originalDigest")
    canonical_digest: str | None = Field(default=None, alias="canonicalDigest")


class ReviewAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ReviewAnchorKind
    start_offset: int = Field(alias="startOffset", ge=0)
    end_offset: int = Field(alias="endOffset", ge=0)
    display_start_offset: int | None = Field(default=None, alias="displayStartOffset", ge=0)
    display_end_offset: int | None = Field(default=None, alias="displayEndOffset", ge=0)
    original_byte_start: int | None = Field(default=None, alias="originalByteStart", ge=0)
    original_byte_end: int | None = Field(default=None, alias="originalByteEnd", ge=0)
    utf16_start: int | None = Field(default=None, alias="utf16Start", ge=0)
    utf16_end: int | None = Field(default=None, alias="utf16End", ge=0)
    quote: str | None = None
    quote_digest: str | None = Field(default=None, alias="quoteDigest")


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewEvidenceStatus
    digest: str | None = None
    highlights: list[ReviewAnchor]


class ReviewReceiptState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ReviewReceiptStatus
    receipt_digest: str | None = Field(default=None, alias="receiptDigest")
    candidate_revision: int = Field(alias="candidateRevision", ge=0)
    source_version_revision: int = Field(alias="sourceVersionRevision", ge=0)


class ReviewProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    semantic_type: str | None = Field(default=None, alias="semanticType")
    predicate: str | None = None


class ManualCaptureInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["human-authored-zero-model"]
    entity_handle: str = Field(alias="entityHandle", pattern=r"^eh1_[0-9a-f]{64}$")


class ReviewWorkbenchDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail_version: Literal["review-workbench.v1"] = Field(alias="detailVersion")
    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    item_handle: str = Field(alias="itemHandle")
    project_scope: Literal["selected"] = Field(alias="projectScope")
    source_version: ReviewSourceVersion = Field(alias="sourceVersion")
    candidate_revision: int = Field(alias="candidateRevision", ge=0)
    label: str
    semantic_type: str = Field(alias="semanticType")
    lifecycle_state: LifecycleState = Field(alias="lifecycleState")
    validation_state: str = Field(alias="validationState")
    constrained_contract_version: str = Field(
        default="constrained-relation.v1", alias="constrainedContractVersion"
    )
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_text: str | None = Field(default=None, alias="sourceText")
    proposed: ReviewProposal
    edited: ReviewProposal | None = None
    evidence: ReviewEvidence
    uncertainty_reasons: list[str] = Field(alias="uncertaintyReasons")
    stale: bool
    quarantined: bool
    abstain_reason: str | None = Field(default=None, alias="abstainReason")
    review_receipt: ReviewReceiptState = Field(alias="reviewReceipt")
    manual_capture: ManualCaptureInfo | None = Field(
        default=None, alias="manualCapture"
    )



class KnowledgeCollectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str
    label: str = Field(min_length=1, max_length=500)
    semantic_type: str = Field(alias="semanticType")
    lifecycle_state: LifecycleState = Field(alias="lifecycleState")
    verification_state: VerificationState = Field(alias="verificationState")
    provenance_state: ProvenanceState = Field(alias="provenanceState")
    valid_from: date | None = Field(default=None, alias="validFrom")
    evidence_count: int = Field(ge=0, alias="evidenceCount")


class KnowledgeCollectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(alias="requestId")
    project_handle: str = Field(alias="projectHandle")
    source_revision: str = Field(alias="sourceRevision")
    stale: bool
    items: list[KnowledgeCollectionItem]
    has_more: bool = Field(alias="hasMore")


def opaque_navigation_handle(value: object, kind: str = "node") -> str:
    """Create a stable, non-reversible-looking handle for a server-side value."""

    if not isinstance(value, str) or not value:
        raise ValueError("navigation handle source is invalid")
    if not kind.isidentifier():
        raise ValueError("navigation handle kind is invalid")
    return f"{kind}-h-{sha256(value.encode('utf-8')).hexdigest()[:24]}"


def require_opaque_handle(value: str, allowed_kinds: tuple[str, ...] = ()) -> str:
    """Reject raw resource syntax and arbitrary identifiers at the public boundary."""

    if not value or any(token in value for token in ("://", "/", "#", "?", "\\")):
        raise ValueError("opaque navigation handle is invalid")
    prefix, separator, digest = value.partition("-h-")
    if not separator or not digest or not digest.isalnum() or len(digest) < 8:
        raise ValueError("opaque navigation handle is invalid")
    if allowed_kinds and prefix not in allowed_kinds:
        raise ValueError("opaque navigation handle kind is not allowlisted")
    return value


def finite_types(values: list[str], allowed: tuple[str, ...], label: str) -> list[str]:
    if any(value not in allowed for value in values):
        raise ValueError(f"{label} is not allowlisted")
    return list(dict.fromkeys(values))


def opaque_or_hashed(value: object, kind: str) -> str:
    if isinstance(value, str) and "-h-" in value:
        try:
            return require_opaque_handle(value)
        except ValueError:
            pass
    return opaque_navigation_handle(value, kind)


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("projection response is invalid")
    return cast(dict[str, object], value)


def required(row: dict[str, object], field: str) -> object:
    """Return one required downstream field without inventing a replacement."""

    if field not in row:
        raise ValueError(f"projection response is missing required field: {field}")
    return row[field]


def required_list(row: dict[str, object], field: str) -> list[object]:
    value = required(row, field)
    if not isinstance(value, list):
        raise ValueError(f"projection response field is not a list: {field}")
    return cast(list[object], value)


def _handle(row: dict[str, object], field: str, kind: str) -> str:
    if field in row:
        return opaque_or_hashed(row[field], kind)
    if "id" in row:
        return opaque_or_hashed(row["id"], kind)
    raise ValueError(f"projection response is missing required handle: {field}")


def project_graph_page(
    payload: object,
    request_id: str,
    project_handle: str,
    node_limit: int,
    edge_limit: int,
) -> GraphProjectionResponse:
    raw = mapping(payload)
    nodes: list[GraphNode] = []
    for item in required_list(raw, "nodes"):
        row = mapping(item)
        row = {**row, "handle": _handle(row, "handle", "node")}
        nodes.append(GraphNode.model_validate(row))
    known_handles = {node.handle for node in nodes}
    edges: list[GraphEdge] = []
    for item in required_list(raw, "edges"):
        row = mapping(item)
        row = {
            **row,
            "handle": _handle(row, "handle", "edge"),
            "sourceHandle": opaque_or_hashed(required(row, "sourceHandle"), "node"),
            "targetHandle": opaque_or_hashed(required(row, "targetHandle"), "node"),
        }
        edge = GraphEdge.model_validate(row)
        if edge.source_handle not in known_handles or edge.target_handle not in known_handles:
            raise ValueError("graph edge references a node outside the finite projection")
        edges.append(edge)
    if len(nodes) > node_limit or len(edges) > edge_limit:
        raise ValueError("graph projection exceeded its published budget")
    page = GraphPageInfo.model_validate(required(raw, "page"))
    if page.node_limit != node_limit or page.edge_limit != edge_limit:
        raise ValueError("graph projection limits do not match the requested budget")
    filters = GraphFilters.model_validate(required(raw, "filters"))
    return GraphProjectionResponse.model_validate(
        {
            "projectionVersion": required(raw, "projectionVersion"),
            "requestId": request_id,
            "projectHandle": project_handle,
            "sourceRevision": required(raw, "sourceRevision"),
            "materializationRevision": required(raw, "materializationRevision"),
            "asOf": required(raw, "asOf"),
            "stale": required(raw, "stale"),
            "partial": required(raw, "partial"),
            "nodes": [node.model_dump(mode="json", by_alias=True) for node in nodes],
            "edges": [edge.model_dump(mode="json", by_alias=True) for edge in edges],
            "page": page.model_dump(mode="json", by_alias=True),
            "filters": filters.model_dump(mode="json", by_alias=True),
        }
    )


def project_node_detail(payload: object, request_id: str, project_handle: str) -> GraphNodeDetail:
    outer = mapping(payload)
    raw = dict(mapping(outer["node"])) if "node" in outer else dict(outer)
    raw.pop("_projecta_http_status", None)
    row = {
        **raw,
        "handle": _handle(raw, "handle", "node"),
        "requestId": request_id,
        "projectHandle": project_handle,
    }
    return GraphNodeDetail.model_validate(row)


def project_link_response(
    payload: object, request_id: str, project_handle: str, node_handle: str, link: str
) -> GraphEvidenceResponse | GraphLifecycleResponse:
    raw = mapping(payload)
    common = {
        "projectionVersion": required(raw, "projectionVersion"),
        "requestId": request_id,
        "projectHandle": project_handle,
        "nodeHandle": node_handle,
        "stale": required(raw, "stale"),
        "items": required_list(raw, "items"),
    }
    if link == "evidence":
        return GraphEvidenceResponse.model_validate(common)
    return GraphLifecycleResponse.model_validate(common)


def project_candidate_queue(
    payload: object, request_id: str, project_handle: str
) -> CandidateQueueResponse:
    raw = mapping(payload)
    items: list[dict[str, object]] = []
    for item in required_list(raw, "candidates"):
        row = mapping(item)
        row = {**row, "handle": _handle(row, "handle", "candidate")}
        items.append(row)
    return CandidateQueueResponse.model_validate(
        {
            "requestId": request_id,
            "projectHandle": project_handle,
            "sourceRevision": required(raw, "sourceRevision"),
            "stale": required(raw, "stale"),
            "candidates": items,
            "hasMore": required(raw, "hasMore"),
        }
    )


def project_review_detail(
    payload: object, request_id: str, project_handle: str, item_handle: str
) -> ReviewWorkbenchDetailResponse:
    """Project one selected candidate into the source-first review contract."""

    raw = mapping(payload)
    candidate = mapping(raw.get("candidate", raw))
    source = mapping(candidate.get("sourceVersion", raw.get("sourceVersion", {})))
    source_revision = _bounded_int(
        source.get("revision", candidate.get("sourceRevision", raw.get("sourceRevision", 0))), 0
    )
    candidate_revision = _bounded_int(
        candidate.get("candidateRevision", candidate.get("revision", 0)), 0
    )
    evidence_raw = mapping(candidate.get("evidence", raw.get("evidence", {})))
    anchors, anchor_error = _review_anchors(
        candidate.get("anchors", candidate.get("highlights", evidence_raw.get("highlights", [])))
    )
    evidence_status = evidence_raw.get("status", "unavailable")
    if evidence_status not in {"selected", "review-required", "abstained", "quarantined", "unavailable"}:
        evidence_status = "quarantined"
    evidence_digest = evidence_raw.get("digest")
    evidence = {
        "status": evidence_status,
        "digest": evidence_digest if isinstance(evidence_digest, str) else None,
        "highlights": anchors,
    }
    stale = candidate.get("stale", raw.get("stale", False)) is True
    quarantined = candidate.get("quarantined", False) is True or anchor_error is not None
    uncertainty = _review_reasons(candidate.get("uncertaintyReasons", []))
    if anchor_error is not None:
        uncertainty.append(anchor_error)
    if stale:
        uncertainty.append("STALE_SOURCE")
    if evidence_status == "unavailable":
        uncertainty.append("EVIDENCE_UNAVAILABLE")
    confidence = candidate.get("confidence")
    bounded_confidence = confidence if isinstance(confidence, (int, float)) and 0 <= confidence <= 1 else None
    receipt = mapping(candidate.get("reviewReceipt", {}))
    receipt_state = receipt.get("state", "not-recorded")
    if receipt_state not in {"not-recorded", "accepted", "rejected", "abstained", "stale", "quarantined"}:
        receipt_state = "quarantined"
    source_text = candidate.get("sourceText", candidate.get("sourceExcerpt"))
    return ReviewWorkbenchDetailResponse.model_validate(
        {
            "detailVersion": "review-workbench.v1",
            "requestId": request_id,
            "projectHandle": project_handle,
            "itemHandle": item_handle,
            "projectScope": "selected",
            "sourceVersion": {
            "revision": source_revision,
            "sourceVersionId": _optional_source_version_id(
                source.get("sourceVersionId", source.get("id"))
            ),
                "canonicalizationVersion": _optional_string(source.get("canonicalizationVersion")),
                "coordinateSystemVersion": _optional_string(source.get("coordinateSystemVersion")),
                "originalDigest": _optional_digest(source.get("originalDigest")),
                "canonicalDigest": _optional_digest(source.get("canonicalDigest")),
            },
            "candidateRevision": candidate_revision,
            "label": _required_display_string(candidate.get("label"), "Selected item"),
            "semanticType": _required_display_string(candidate.get("proposedType"), "Unknown"),
            "lifecycleState": _lifecycle(candidate.get("lifecycleState")),
            "validationState": _required_display_string(candidate.get("validationState"), "unavailable"),
            "constrainedContractVersion": _required_display_string(
                candidate.get("constrainedContractVersion"), "constrained-relation.v1"
            ),
            "confidence": bounded_confidence,
            "sourceText": source_text if isinstance(source_text, str) else None,
            "proposed": {
                "label": _optional_string(candidate.get("label")),
                "semanticType": _optional_string(candidate.get("proposedType")),
                "predicate": _optional_string(candidate.get("predicate")),
            },
            "edited": _review_proposal(candidate.get("edited")),
            "evidence": evidence,
            "uncertaintyReasons": list(dict.fromkeys(uncertainty)),
            "stale": stale,
            "quarantined": quarantined,
            "abstainReason": _optional_string(candidate.get("abstainReason"))
            or ("INVALID_SOURCE_ANCHOR" if anchor_error else None),
            "reviewReceipt": {
                "state": receipt_state,
                "receiptDigest": _optional_digest(receipt.get("receiptDigest")),
                "candidateRevision": _bounded_int(receipt.get("candidateRevision", candidate_revision), 0),
                "sourceVersionRevision": _bounded_int(
                    receipt.get("sourceVersionRevision", source_revision), 0
                ),
            },
            "manualCapture": raw.get("manualCapture"),
        }
    )


def _review_anchors(value: object) -> tuple[list[dict[str, object]], str | None]:
    if value is None:
        return [], None
    if not isinstance(value, list):
        return [], "INVALID_SOURCE_ANCHOR"
    result: list[dict[str, object]] = []
    for item in cast(list[object], value):
        row = mapping(item)
        start = row.get("startOffset")
        end = row.get("endOffset")
        kind = row.get("kind", "evidence")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start:
            return [], "INVALID_SOURCE_ANCHOR"
        if kind not in {"endpoint", "trigger", "evidence"}:
            return [], "INVALID_SOURCE_ANCHOR"
        result.append(
            {
                "kind": kind,
                "startOffset": start,
                "endOffset": end,
                "displayStartOffset": _optional_nonnegative(row.get("displayStartOffset")),
                "displayEndOffset": _optional_nonnegative(row.get("displayEndOffset")),
                "originalByteStart": _optional_nonnegative(row.get("originalByteStart")),
                "originalByteEnd": _optional_nonnegative(row.get("originalByteEnd")),
                "utf16Start": _optional_nonnegative(row.get("utf16Start")),
                "utf16End": _optional_nonnegative(row.get("utf16End")),
                "quote": row.get("quote") if isinstance(row.get("quote"), str) else None,
                "quoteDigest": _optional_digest(row.get("quoteDigest")),
            }
        )
    return result, None


def _review_reasons(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    allowed = {
        "LOW_CONFIDENCE",
        "EVIDENCE_UNAVAILABLE",
        "STALE_SOURCE",
        "QUARANTINED_ITEM",
        "VALIDATION_REQUIRED",
        "AMBIGUOUS_RELATION",
    }
    return [item if isinstance(item, str) and item in allowed else "UNSPECIFIED" for item in value]


def _review_proposal(value: object) -> dict[str, str | None] | None:
    if not isinstance(value, dict):
        return None
    row = cast(dict[object, object], value)
    return {
        "label": _optional_string(row.get("label")),
        "semanticType": _optional_string(row.get("semanticType", row.get("type"))),
        "predicate": _optional_string(row.get("predicate")),
    }


def _bounded_int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default


def _optional_nonnegative(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_digest(value: object) -> str | None:
    return value if isinstance(value, str) and value.startswith("sha256:") else None


def _optional_source_version_id(value: object) -> str | None:
    return value if isinstance(value, str) and value.startswith("sv_") and len(value) == 67 else None


def _required_display_string(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _lifecycle(value: object) -> LifecycleState:
    return cast(LifecycleState, value) if value in {
        "current", "pending-review", "confirmed", "rejected", "superseded", "retracted", "stale"
    } else "pending-review"


def project_knowledge_collection(
    payload: object, request_id: str, project_handle: str
) -> KnowledgeCollectionResponse:
    raw = mapping(payload)
    items: list[dict[str, object]] = []
    for item in required_list(raw, "items"):
        row = mapping(item)
        row = {**row, "handle": _handle(row, "handle", "knowledge")}
        items.append(row)
    return KnowledgeCollectionResponse.model_validate(
        {
            "requestId": request_id,
            "projectHandle": project_handle,
            "sourceRevision": required(raw, "sourceRevision"),
            "stale": required(raw, "stale"),
            "items": items,
            "hasMore": required(raw, "hasMore"),
        }
    )
