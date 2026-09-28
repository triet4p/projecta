"""Versioned, non-materializing constrained relation contract (RM-60)."""

from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from projecta_api.extraction.confirmed_entity_gate import EntityHandle, RelationAuthorization
from projecta_api.extraction.relation_evidence_selection import RelationEvidenceSelection
from projecta_api.extraction.source_version import SourceVersion

CONSTRAINED_RELATION_CONTRACT_VERSION: Final = "constrained-relation.v1"
ONTOLOGY_CONTRACT_VERSION: Final = "ontology.v0.5.1"

ConstrainedOutcome = Literal["review-pending", "abstained", "quarantined"]
ConstrainedReason = Literal[
    "REVIEW_PENDING",
    "SOURCE_MISSING",
    "PROJECT_MISMATCH",
    "SOURCE_VERSION_MISMATCH",
    "UNKNOWN_CONTRACT_VERSION",
    "HANDLE_MISMATCH",
    "TYPE_VERSION_MISMATCH",
    "STALE_CONFIRMATION",
    "UNSUPPORTED_PREDICATE",
    "UNSUPPORTED_DIRECTION",
    "SELF_RELATION",
    "EVIDENCE_REQUIRED",
    "EVIDENCE_STATUS_INVALID",
    "EVIDENCE_DIGEST_MISMATCH",
    "AMBIGUOUS_POLARITY",
    "AMBIGUOUS_MODALITY",
    "AMBIGUOUS_TEMPORAL",
    "UNSUPPORTED_POLARITY",
    "UNSUPPORTED_MODALITY",
    "UNSUPPORTED_TEMPORAL",
    "MALFORMED_REQUEST",
]

_PREDICATE_TYPES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "implements": (
        frozenset({"Task", "Decision", "Requirement"}),
        frozenset({"Requirement", "Decision", "Constraint"}),
    ),
    "blocks": (frozenset({"Requirement", "Decision", "Task", "Risk"}), frozenset({"Requirement", "Decision", "Task", "Risk"})),
    "dependsOn": (frozenset({"Requirement", "Decision", "Task", "Risk"}), frozenset({"Requirement", "Decision", "Task", "Risk"})),
    "supports": (frozenset({"Requirement", "Decision", "Task", "Risk", "Question", "ResearchFinding"}), frozenset({"Requirement", "Decision", "Task", "Risk", "Question", "ResearchFinding"})),
    "answers": (
        frozenset({"Question", "ResearchFinding", "Task"}),
        frozenset({"Question", "Requirement", "Decision", "ResearchFinding"}),
    ),
    "resolves": (frozenset({"Requirement", "Decision", "Task", "Risk"}), frozenset({"Risk", "Question", "Requirement", "Decision"})),
    "constrainedBy": (frozenset({"Requirement", "Decision", "Task"}), frozenset({"Constraint"})),
}

def allowed_relation_predicates(source_type: str, target_type: str) -> list[str]:
    """Return predicates whose server-owned direction matrix accepts these endpoint types."""
    return [
        predicate
        for predicate, (source_types, target_types) in _PREDICATE_TYPES.items()
        if source_type in source_types and target_type in target_types
    ]


def relation_direction_allowed(predicate: str, source_type: str, target_type: str) -> bool:
    """Check one predicate against the canonical relation endpoint-type matrix."""
    source_types, target_types = _PREDICATE_TYPES.get(predicate, (frozenset(), frozenset()))
    return source_type in source_types and target_type in target_types

_POLARITIES: frozenset[str] = frozenset({"positive", "negative", "unknown"})
_MODALITIES: frozenset[str] = frozenset({"asserted", "possible", "planned", "conditional", "unknown"})
_TEMPORAL: frozenset[str] = frozenset({"before", "after", "during", "at", "until", "since"})


class ConstrainedRelationContractError(ValueError):
    """Raised only for malformed API calls; semantic misses are finite outcomes."""

    def __init__(self, reason: ConstrainedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class TemporalQualifier(BaseModel):
    """Normalized temporal qualifier; raw temporal prose is never serialized."""

    model_config = ConfigDict(extra="forbid")

    kind: str | None = None
    value: str | None = None
    ambiguous: bool = False


class ConstrainedRelationRequest(BaseModel):
    """Input binding handles, authorization, selected evidence, and semantics."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["constrained-relation.v1"] = Field(
        default=CONSTRAINED_RELATION_CONTRACT_VERSION, alias="contractVersion"
    )
    ontology_version: str = Field(default=ONTOLOGY_CONTRACT_VERSION, alias="ontologyVersion")
    authorization: RelationAuthorization
    source_handle: EntityHandle = Field(alias="sourceHandle")
    target_handle: EntityHandle = Field(alias="targetHandle")
    evidence: RelationEvidenceSelection | None = None
    evidence_status: str = Field(alias="evidenceStatus")
    evidence_digest: str | None = Field(default=None, alias="evidenceDigest")
    polarity: str
    modality: str
    temporal: TemporalQualifier = Field(default_factory=TemporalQualifier)


class ConstrainedRelationResult(BaseModel):
    """Safe outcome; this contract can never produce asserted/materializable state."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["constrained-relation.v1"] = Field(
        default=CONSTRAINED_RELATION_CONTRACT_VERSION, alias="contractVersion"
    )
    outcome: ConstrainedOutcome
    reason: ConstrainedReason
    materializable: bool = False
    ontology_version: Literal["ontology.v0.5.1"] = Field(
        default=ONTOLOGY_CONTRACT_VERSION, alias="ontologyVersion"
    )
    predicate: str
    polarity: str
    modality: str
    temporal_kind: str | None = Field(default=None, alias="temporalKind")
    temporal_value_digest: str | None = Field(default=None, alias="temporalValueDigest")
    evidence_status: str = Field(alias="evidenceStatus")
    evidence_digest: str | None = Field(default=None, alias="evidenceDigest")
    relation_digest: str = Field(alias="relationDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    source_handle_digest: str = Field(alias="sourceHandleDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    target_handle_digest: str = Field(alias="targetHandleDigest", pattern=r"^sha256:[0-9a-f]{64}$")
    source_confirmation_revision_digest: str = Field(
        alias="sourceConfirmationRevisionDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    target_confirmation_revision_digest: str = Field(
        alias="targetConfirmationRevisionDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )

    @model_validator(mode="after")
    def forbid_materialization(self) -> ConstrainedRelationResult:
        if self.materializable or self.outcome not in {"review-pending", "abstained", "quarantined"}:
            raise ValueError("constrained relation contract never materializes or asserts")
        return self

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


def constrain_relation(
    project_id: str,
    source: SourceVersion | None,
    request: ConstrainedRelationRequest,
) -> ConstrainedRelationResult:
    """Validate semantics and return review-pending only for an unambiguous contract."""

    if source is None:
        return _result(request, "abstained", "SOURCE_MISSING")
    if source.project_id != project_id:
        return _result(request, "quarantined", "PROJECT_MISMATCH")
    if request.contract_version != CONSTRAINED_RELATION_CONTRACT_VERSION or request.ontology_version != ONTOLOGY_CONTRACT_VERSION:
        return _result(request, "quarantined", "UNKNOWN_CONTRACT_VERSION")
    authorization = request.authorization
    if (
        authorization.contract_version != "relation-gate.v1"
        or request.source_handle.contract_version != "entity-handle.v1"
        or request.target_handle.contract_version != "entity-handle.v1"
    ):
        return _result(request, "quarantined", "UNKNOWN_CONTRACT_VERSION")
    if authorization.source_version_id != source.source_version_id:
        return _result(request, "abstained", "SOURCE_VERSION_MISMATCH")
    if request.source_handle.handle == request.target_handle.handle:
        return _result(request, "abstained", "SELF_RELATION")
    if (
        request.source_handle.handle != authorization.source_handle
        or request.target_handle.handle != authorization.target_handle
    ):
        return _result(request, "quarantined", "HANDLE_MISMATCH")
    if (
        request.source_handle.source_version_id != source.source_version_id
        or request.target_handle.source_version_id != source.source_version_id
        or request.source_handle.project_scope_id != source.project_scope_id
        or request.target_handle.project_scope_id != source.project_scope_id
    ):
        return _result(request, "quarantined", "PROJECT_MISMATCH")
    if authorization.predicate not in _PREDICATE_TYPES:
        return _result(request, "abstained", "UNSUPPORTED_PREDICATE")
    source_types, target_types = _PREDICATE_TYPES[authorization.predicate]
    if request.source_handle.entity_type not in source_types or request.target_handle.entity_type not in target_types:
        return _result(request, "abstained", "UNSUPPORTED_DIRECTION")
    if request.evidence is None:
        return _result(request, "abstained", "EVIDENCE_REQUIRED")
    if request.evidence.contract_version != "relation-evidence.v1" or request.evidence.source_version_id != source.source_version_id:
        return _result(request, "abstained", "SOURCE_VERSION_MISMATCH")
    if request.evidence.relation_id != authorization.relation_id:
        return _result(request, "quarantined", "EVIDENCE_DIGEST_MISMATCH")
    if request.evidence.outcome != "selected" or request.evidence.reason != "SELECTED" or not request.evidence.materializable:
        return _result(request, "abstained", "EVIDENCE_STATUS_INVALID")
    expected_evidence_digest = _digest(_stable_json(request.evidence.safe_dict()))
    if request.evidence_digest != expected_evidence_digest:
        return _result(request, "quarantined", "EVIDENCE_DIGEST_MISMATCH")
    if request.evidence_status != "selected":
        return _result(request, "abstained", "EVIDENCE_STATUS_INVALID")
    if request.polarity not in _POLARITIES:
        return _result(request, "abstained", "UNSUPPORTED_POLARITY")
    if request.polarity == "unknown":
        return _result(request, "abstained", "AMBIGUOUS_POLARITY")
    if request.modality not in _MODALITIES:
        return _result(request, "abstained", "UNSUPPORTED_MODALITY")
    if request.modality == "unknown":
        return _result(request, "abstained", "AMBIGUOUS_MODALITY")
    if request.temporal.ambiguous:
        return _result(request, "abstained", "AMBIGUOUS_TEMPORAL")
    if request.temporal.kind is not None and request.temporal.kind not in _TEMPORAL:
        return _result(request, "abstained", "UNSUPPORTED_TEMPORAL")
    if request.temporal.kind is not None and not request.temporal.value:
        return _result(request, "abstained", "AMBIGUOUS_TEMPORAL")
    return _result(request, "review-pending", "REVIEW_PENDING")


def serialize_constrained_relation(result: ConstrainedRelationResult) -> str:
    return json.dumps(result.safe_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _result(
    request: ConstrainedRelationRequest, outcome: ConstrainedOutcome, reason: ConstrainedReason
) -> ConstrainedRelationResult:
    evidence_digest = request.evidence_digest
    return ConstrainedRelationResult(
        outcome=outcome,
        reason=reason,
        predicate=request.authorization.predicate,
        polarity=request.polarity,
        modality=request.modality,
        temporalKind=request.temporal.kind,
        temporalValueDigest=_digest(request.temporal.value.encode("utf-8")) if request.temporal.value else None,
        evidenceStatus=request.evidence_status,
        evidenceDigest=evidence_digest,
        relationDigest=_digest(request.authorization.relation_id.encode("utf-8")),
        sourceHandleDigest=_digest(request.source_handle.handle.encode("utf-8")),
        targetHandleDigest=_digest(request.target_handle.handle.encode("utf-8")),
        sourceConfirmationRevisionDigest=_digest(request.source_handle.confirmation_revision.encode("utf-8")),
        targetConfirmationRevisionDigest=_digest(request.target_handle.confirmation_revision.encode("utf-8")),
    )


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _stable_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8", "strict")
