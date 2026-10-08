"""Deterministic relation context from current, receipt-confirmed manual captures."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from projecta_api.extraction.confirmed_entity_gate import EntityHandle, RelationAuthorization
from projecta_api.extraction.constrained_relation import allowed_relation_predicates
from projecta_api.extraction.contracts import RelationPredicate
from projecta_api.extraction.manual_capture import VerifiedManualCapture
from projecta_api.extraction.relation_evidence_selection import (
    RelationEvidenceSelection,
    select_relation_evidence,
)
from projecta_api.extraction.review_receipts import ReviewDecisionReceiptRecord
from projecta_api.structured_note import CandidateEditType

RelationDirection = Literal["source-to-target", "target-to-source"]
RelationSuggestionMode = Literal["manual", "local"]
RelationDecision = Literal["confirm", "reject"]


class ControlledRelationRequest(BaseModel):
    """Select a confirmed endpoint pair and choose manual or local predicate assistance."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    target_candidate_handle: str = Field(alias="targetCandidateHandle", min_length=1, max_length=128)
    direction: RelationDirection
    mode: RelationSuggestionMode
    predicate: str | None = Field(default=None, min_length=1, max_length=64)
    retry: bool = False

    @model_validator(mode="after")
    def validate_mode_fields(self) -> ControlledRelationRequest:
        if (self.mode == "manual") != (self.predicate is not None):
            raise ValueError("manual mode requires only an explicit predicate")
        if self.mode == "manual" and self.retry:
            raise ValueError("manual relation suggestions cannot retry inference")
        return self


class ControlledRelationDecisionRequest(BaseModel):
    """Record an explicit confirm or reject decision against one proposal revision."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    expected_revision: int = Field(alias="expectedProposalRevision", ge=1)
    decision: RelationDecision
    reason: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_reason(self) -> ControlledRelationDecisionRequest:
        if self.decision != "reject" and self.reason is not None:
            raise ValueError("reason is accepted only for rejection")
        return self


class RelationSuggestionTarget(BaseModel):
    """Same-source, receipt-confirmed endpoint offered for explicit pairing."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    candidate_handle: str = Field(alias="candidateHandle", min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)
    entity_type: str = Field(alias="entityType", min_length=1, max_length=64)
    allowed_predicates: dict[RelationDirection, list[str]] = Field(alias="allowedPredicates")


class RelationSuggestionTargetsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(alias="requestId", min_length=1)
    targets: list[RelationSuggestionTarget]


@dataclass(frozen=True, slots=True)
class ControlledRelationEndpoint:
    """Server-resolved manual capture identity and its current confirmation receipt."""

    candidate_handle: str
    entity_handle: str
    capture: VerifiedManualCapture
    confirmation: ReviewDecisionReceiptRecord


@dataclass(frozen=True, slots=True)
class RelationSuggestionOption:
    """One predicate option with server-resolved endpoint identities and evidence."""

    relation_id: str
    predicate: RelationPredicate
    source_handle: str
    target_handle: str
    source_candidate_handle: str
    target_candidate_handle: str
    direction: RelationDirection
    evidence_digest: str
    evidence: RelationEvidenceSelection


@dataclass(frozen=True, slots=True)
class RelationSuggestionContext:
    """Trusted relation data; only predicate labels are exposed to local inference."""

    selected_candidate_handle: str
    target_candidate_handle: str
    direction: RelationDirection
    source_handle: str
    target_handle: str
    source_candidate_handle: str
    semantic_target_candidate_handle: str
    source_label: str
    target_label: str
    source_type: CandidateEditType
    target_type: CandidateEditType
    allowed_predicates: tuple[str, ...]
    options: tuple[RelationSuggestionOption, ...]
    evidence_digest: str

    def option_for(self, predicate: str) -> RelationSuggestionOption | None:
        return next((option for option in self.options if option.predicate == predicate), None)


def allowed_predicates_by_direction(
    source_type: str, target_type: str
) -> dict[RelationDirection, list[RelationPredicate]]:
    """Return only the server's supported predicate/type matrix for each orientation."""

    return {
        "source-to-target": allowed_relation_predicates(source_type, target_type),
        "target-to-source": allowed_relation_predicates(target_type, source_type),
    }


def build_relation_suggestion_context(
    project_id: str,
    selected: ControlledRelationEndpoint,
    target: ControlledRelationEndpoint,
    direction: RelationDirection,
) -> RelationSuggestionContext:
    """Resolve direction and deterministic evidence from two current confirmed anchors."""

    _validate_endpoint(project_id, selected)
    _validate_endpoint(project_id, target)
    if selected.candidate_handle == target.candidate_handle:
        raise ValueError("relation endpoints must be distinct")
    source_version = selected.capture.source_version
    if (
        target.capture.source_version.source_version_id != source_version.source_version_id
        or target.capture.source_text != selected.capture.source_text
    ):
        raise ValueError("relation endpoints must share one current source version")

    semantic_source, semantic_target = (
        (selected, target) if direction == "source-to-target" else (target, selected)
    )
    predicates = allowed_relation_predicates(
        semantic_source.capture.entity_type, semantic_target.capture.entity_type
    )
    source_entity = _entity_handle(semantic_source)
    target_entity = _entity_handle(semantic_target)
    options: list[RelationSuggestionOption] = []
    for predicate in predicates:
        relation_id = _relation_id(project_id, source_version.source_version_id, semantic_source, semantic_target, predicate)
        authorization = RelationAuthorization(
            relationId=relation_id,
            sourceHandle=source_entity.handle,
            targetHandle=target_entity.handle,
            predicate=predicate,
            sourceVersionId=source_version.source_version_id,
            idempotentReplay=False,
        )
        evidence = select_relation_evidence(
            project_id,
            source_version,
            selected.capture.source_text,
            authorization,
            semantic_source.capture.anchor,
            semantic_target.capture.anchor,
        )
        if evidence.outcome != "selected" or not evidence.materializable:
            continue
        evidence_digest = _digest(_stable_json(evidence.safe_dict()))
        options.append(
            RelationSuggestionOption(
                relation_id=relation_id,
                predicate=predicate,
                source_handle=source_entity.handle,
                target_handle=target_entity.handle,
                source_candidate_handle=semantic_source.candidate_handle,
                target_candidate_handle=semantic_target.candidate_handle,
                direction=direction,
                evidence_digest=evidence_digest,
                evidence=evidence,
            )
        )

    key_digest = _digest(
        _stable_json(
            {
                "projectDigest": _digest(project_id.encode("utf-8", "strict")),
                "sourceVersionId": source_version.source_version_id,
                "direction": direction,
                "selectedCandidate": selected.candidate_handle,
                "targetCandidate": target.candidate_handle,
                "selectedRevision": selected.capture.candidate_revision,
                "targetRevision": target.capture.candidate_revision,
                "selectedAnchorDigest": selected.capture.anchor.quote_digest,
                "targetAnchorDigest": target.capture.anchor.quote_digest,
                "selectedAnchorRange": [
                    selected.capture.anchor.start_offset,
                    selected.capture.anchor.end_offset,
                ],
                "targetAnchorRange": [
                    target.capture.anchor.start_offset,
                    target.capture.anchor.end_offset,
                ],
                "selectedReceiptDigest": selected.confirmation.receipt_digest,
                "targetReceiptDigest": target.confirmation.receipt_digest,
                "allowedPredicates": [option.predicate for option in options],
            }
        )
    )
    return RelationSuggestionContext(
        selected_candidate_handle=selected.candidate_handle,
        target_candidate_handle=target.candidate_handle,
        direction=direction,
        source_handle=source_entity.handle,
        target_handle=target_entity.handle,
        source_candidate_handle=semantic_source.candidate_handle,
        semantic_target_candidate_handle=semantic_target.candidate_handle,
        source_label=semantic_source.capture.evidence_text,
        target_label=semantic_target.capture.evidence_text,
        source_type=semantic_source.capture.entity_type,
        target_type=semantic_target.capture.entity_type,
        allowed_predicates=tuple(option.predicate for option in options),
        options=tuple(options),
        evidence_digest=key_digest,
    )


def relation_workflow_item_handle(
    selected_candidate_handle: str,
    target_candidate_handle: str,
    direction: RelationDirection,
    mode: RelationSuggestionMode,
    predicate: str | None,
) -> str:
    """Produce a private opaque cache component for one controlled endpoint workflow."""

    return "relation-workflow-" + hashlib.sha256(
        _stable_json(
            {
                "selectedCandidate": selected_candidate_handle,
                "targetCandidate": target_candidate_handle,
                "direction": direction,
                "mode": mode,
                "predicate": predicate,
            }
        )
    ).hexdigest()


def _validate_endpoint(project_id: str, endpoint: ControlledRelationEndpoint) -> None:
    capture = endpoint.capture
    receipt = endpoint.confirmation
    source_digest = _digest(capture.source_version.source_version_id.encode("utf-8", "strict"))
    if capture.source_version.project_id != project_id:
        raise ValueError("relation endpoint belongs to another project")
    if capture.candidate_status != "validated":
        raise ValueError("relation endpoint is not validated")
    if (
        receipt.item_kind != "entity"
        or receipt.decision != "confirm"
        or receipt.candidate_revision != capture.candidate_revision
        or receipt.source_version_digest != source_digest
        or receipt.source_version_revision != 1
        or receipt.constrained_contract_version != "manual-entity-capture.v1"
        or receipt.evidence_digest != capture.anchor.quote_digest
    ):
        raise ValueError("relation endpoint confirmation is stale")


def _entity_handle(endpoint: ControlledRelationEndpoint) -> EntityHandle:
    revision = "rev_" + hashlib.sha256(
        endpoint.confirmation.receipt_digest.encode("utf-8", "strict")
    ).hexdigest()
    return EntityHandle(
        handle=endpoint.entity_handle,
        projectScopeId=endpoint.capture.source_version.project_scope_id,
        sourceVersionId=endpoint.capture.source_version.source_version_id,
        entityType=endpoint.capture.entity_type,
        confirmationRevision=revision,
    )


def _relation_id(
    project_id: str,
    source_version_id: str,
    source: ControlledRelationEndpoint,
    target: ControlledRelationEndpoint,
    predicate: str,
) -> str:
    fingerprint = _stable_json(
        {
            "projectDigest": _digest(project_id.encode("utf-8", "strict")),
            "sourceVersionId": source_version_id,
            "sourceHandle": source.entity_handle,
            "targetHandle": target.entity_handle,
            "predicate": predicate,
            "sourceAnchorDigest": source.capture.anchor.quote_digest,
            "targetAnchorDigest": target.capture.anchor.quote_digest,
            "sourceConfirmationDigest": source.confirmation.receipt_digest,
            "targetConfirmationDigest": target.confirmation.receipt_digest,
        }
    )
    return "rel_" + hashlib.sha256(fingerprint).hexdigest()


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _stable_json(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8", "strict"
    )
