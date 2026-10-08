"""Opt-in, per-item validation and quarantine for extraction candidates."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from projecta_api.extraction.source_version import SourceVersion
from projecta_api.extraction.text_anchor import (
    TextAnchor,
    TextAnchorVerificationError,
    verify_text_anchor,
)

ITEM_VALIDATION_CONTRACT_VERSION: Final = "item-validation.v1"

ItemKind = Literal["entity", "entity-link", "relation", "evidence"]
ReportedItemKind = Literal["entity", "entity-link", "relation", "evidence", "unknown"]
LifecycleOutcome = Literal[
    "contract-valid", "review-pending", "abstained", "quarantined", "stale"
]
ItemValidationReason = Literal[
    "VALID",
    "REVIEW_REQUIRED",
    "ABSTAINED",
    "QUARANTINED",
    "STALE",
    "UNKNOWN_KIND",
    "UNKNOWN_STATUS",
    "UNKNOWN_REASON",
    "UNKNOWN_SCHEMA_FIELD",
    "UNSUPPORTED_SCHEMA_VERSION",
    "MALFORMED_ITEM",
    "PROJECT_MISMATCH",
    "SOURCE_MISSING",
    "SOURCE_VERSION_MISMATCH",
    "SOURCE_TAMPERED",
    "SOURCE_STALE",
    "ANCHOR_MISSING",
    "ANCHOR_INVALID",
    "INVALID_INPUT_REASON",
    "UNSUPPORTED_COORDINATE_VERSION",
    "EXACT_QUOTE_MISMATCH",
    "QUOTE_DIGEST_MISMATCH",
    "MAPPING_MISMATCH",
    "NEGATIVE_OFFSET",
    "REVERSED_RANGE",
    "EMPTY_RANGE",
    "OUT_OF_RANGE",
    "INVALID_UNICODE",
    "MISSING_QUOTE",
    "AMBIGUOUS_REPEATED_QUOTE",
    "OCCURRENCE_OUT_OF_RANGE",
]

_KINDS: frozenset[str] = frozenset({"entity", "entity-link", "relation", "evidence"})
_STATUSES: frozenset[str] = frozenset(
    {"candidate", "review-pending", "abstained", "quarantined", "stale"}
)
_INPUT_REASONS: frozenset[str] = frozenset(
    {"VALID", "REVIEW_REQUIRED", "ABSTAINED", "QUARANTINED", "STALE"}
)
_ITEM_KEYS: frozenset[str] = frozenset(
    {
        "schemaVersion",
        "itemId",
        "kind",
        "status",
        "reason",
        "projectId",
        "sourceVersionId",
        "anchor",
        "payload",
    }
)
_PAYLOAD_KEYS: dict[str, frozenset[str]] = {
    "entity": frozenset({"type", "label", "candidateId"}),
    "entity-link": frozenset({"mention", "targetEntityId"}),
    "relation": frozenset({"predicate", "sourceEntityId", "targetEntityId"}),
    "evidence": frozenset(),
}
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "Requirement",
        "Decision",
        "Question",
        "Task",
        "Risk",
        "Assumption",
        "Constraint",
        "ProgressClaim",
        "ResearchFinding",
    }
)
_RELATION_PREDICATES: frozenset[str] = frozenset(
    {"implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"}
)


class ItemMaterializationError(ValueError):
    """Raised when a non-valid item is presented to a materialization boundary."""

    def __init__(self, reason: ItemValidationReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ItemValidationResult(BaseModel):
    """Raw-data-free, independently classified item outcome."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["item-validation.v1"] = Field(
        default=ITEM_VALIDATION_CONTRACT_VERSION, alias="contractVersion"
    )
    item_index: int = Field(ge=0, alias="itemIndex")
    kind: ReportedItemKind
    outcome: LifecycleOutcome
    reason: ItemValidationReason
    materializable: bool
    source_version_id: str | None = Field(default=None, alias="sourceVersionId")

    @model_validator(mode="after")
    def enforce_materialization_guard(self) -> ItemValidationResult:
        expected = self.outcome == "contract-valid" and self.reason == "VALID"
        if self.materializable != expected:
            raise ValueError("only a contract-valid item with VALID reason is materializable")
        return self

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


class ItemValidationBatch(BaseModel):
    """Deterministic ordered results; one failure never drops another result."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["item-validation.v1"] = Field(
        default=ITEM_VALIDATION_CONTRACT_VERSION, alias="contractVersion"
    )
    results: list[ItemValidationResult]

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


def validate_item_batch(
    project_id: str,
    source: SourceVersion | None,
    content: bytes | str | None,
    items: Sequence[object],
) -> ItemValidationBatch:
    """Classify every item independently against a verified source boundary."""

    results = [
        _classify_item(project_id, source, content, item, index)
        for index, item in enumerate(items)
    ]
    return ItemValidationBatch(results=results)


def can_materialize(result: ItemValidationResult) -> bool:
    """Recheck the guard at the downstream boundary, including untrusted copies."""

    return (
        result.outcome == "contract-valid"
        and result.reason == "VALID"
        and result.materializable is True
    )


def require_materializable(result: ItemValidationResult) -> None:
    """Fail closed before any downstream mutation is attempted."""

    if not can_materialize(result):
        raise ItemMaterializationError(result.reason)


def serialize_item_validation(batch: ItemValidationBatch) -> str:
    """Serialize only deterministic validation metadata, never item payloads."""

    return json.dumps(batch.safe_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _classify_item(
    project_id: str,
    source: SourceVersion | None,
    content: bytes | str | None,
    item: object,
    index: int,
) -> ItemValidationResult:
    if not isinstance(item, Mapping):
        return _result(index, "unknown", "quarantined", "MALFORMED_ITEM", source)
    typed_item: Mapping[str, object] = cast(Mapping[str, object], item)
    unknown_keys: set[str] = set(typed_item) - set(_ITEM_KEYS)
    if unknown_keys:
        return _result(index, _reported_kind(typed_item.get("kind")), "quarantined", "UNKNOWN_SCHEMA_FIELD", source)
    if typed_item.get("schemaVersion") != ITEM_VALIDATION_CONTRACT_VERSION:
        reason: ItemValidationReason = (
            "UNSUPPORTED_SCHEMA_VERSION"
            if typed_item.get("schemaVersion") is not None
            else "MALFORMED_ITEM"
        )
        return _result(index, _reported_kind(typed_item.get("kind")), "quarantined", reason, source)
    kind_value: object = typed_item.get("kind")
    if not isinstance(kind_value, str) or kind_value not in _KINDS:
        return _result(index, "unknown", "quarantined", "UNKNOWN_KIND", source)
    raw_status: object = typed_item.get("status", "candidate")
    if not isinstance(raw_status, str) or raw_status not in _STATUSES:
        return _result(index, cast(ItemKind, kind_value), "quarantined", "UNKNOWN_STATUS", source)
    raw_reason: object = typed_item.get("reason", "VALID")
    if not isinstance(raw_reason, str) or raw_reason not in _INPUT_REASONS:
        return _result(index, cast(ItemKind, kind_value), "quarantined", "UNKNOWN_REASON", source)
    project_value: object = typed_item.get("projectId")
    if not isinstance(project_value, str) or project_value != project_id:
        return _result(index, cast(ItemKind, kind_value), "quarantined", "PROJECT_MISMATCH", source)
    if source is None or content is None:
        return _result(index, cast(ItemKind, kind_value), "quarantined", "SOURCE_MISSING", source)
    source_version_id: object = typed_item.get("sourceVersionId")
    if not isinstance(source_version_id, str) or source_version_id != source.source_version_id:
        return _result(index, cast(ItemKind, kind_value), "stale", "SOURCE_VERSION_MISMATCH", source)
    if source.project_id != project_id:
        return _result(index, cast(ItemKind, kind_value), "quarantined", "PROJECT_MISMATCH", source)
    payload: object = typed_item.get("payload")
    payload_reason = _validate_payload(kind_value, payload)
    if payload_reason is not None:
        return _result(index, cast(ItemKind, kind_value), "quarantined", payload_reason, source)
    anchor_value: object = typed_item.get("anchor")
    if anchor_value is None:
        return _result(index, cast(ItemKind, kind_value), "quarantined", "ANCHOR_MISSING", source)
    try:
        anchor = anchor_value if isinstance(anchor_value, TextAnchor) else TextAnchor.model_validate(anchor_value)
        verify_text_anchor(anchor, source, content)
    except TextAnchorVerificationError as error:
        anchor_failure = _anchor_reason(error.reason)
        outcome: LifecycleOutcome = "stale" if anchor_failure in {"SOURCE_STALE", "SOURCE_VERSION_MISMATCH"} else "quarantined"
        return _result(index, cast(ItemKind, kind_value), outcome, anchor_failure, source)
    except (TypeError, ValueError):
        return _result(index, cast(ItemKind, kind_value), "quarantined", "ANCHOR_INVALID", source)
    outcome, outcome_reason = _lifecycle(raw_status, raw_reason)
    return _result(index, cast(ItemKind, kind_value), outcome, outcome_reason, source)


def _validate_payload(kind: str, payload: object) -> ItemValidationReason | None:
    if not isinstance(payload, Mapping):
        return "MALFORMED_ITEM"
    typed_payload: Mapping[str, object] = cast(Mapping[str, object], payload)
    if set(typed_payload) - _PAYLOAD_KEYS[kind]:
        return "UNKNOWN_SCHEMA_FIELD"
    if kind == "evidence":
        return None if not typed_payload else "UNKNOWN_SCHEMA_FIELD"
    required = {
        "entity": ("type", "label"),
        "entity-link": ("mention", "targetEntityId"),
        "relation": ("predicate", "sourceEntityId", "targetEntityId"),
    }[kind]
    if any(key not in typed_payload for key in required):
        return "MALFORMED_ITEM"
    for key in required:
        value: object = typed_payload[key]
        if not isinstance(value, str) or not value.strip():
            return "MALFORMED_ITEM"
        if key.endswith("EntityId") and not _OPAQUE_ID.fullmatch(value):
            return "MALFORMED_ITEM"
    if kind == "entity" and typed_payload["type"] not in _ENTITY_TYPES:
        return "MALFORMED_ITEM"
    if kind == "relation" and typed_payload["predicate"] not in _RELATION_PREDICATES:
        return "MALFORMED_ITEM"
    candidate_value: object = typed_payload.get("candidateId")
    if "candidateId" in typed_payload and candidate_value is not None:
        if not isinstance(candidate_value, str) or not _OPAQUE_ID.fullmatch(candidate_value):
            return "MALFORMED_ITEM"
    return None


def _lifecycle(status: str, reason: str) -> tuple[LifecycleOutcome, ItemValidationReason]:
    if status == "review-pending" or reason == "REVIEW_REQUIRED":
        return "review-pending", "REVIEW_REQUIRED"
    if status == "abstained" or reason == "ABSTAINED":
        return "abstained", "ABSTAINED"
    if status == "quarantined" or reason == "QUARANTINED":
        return "quarantined", "QUARANTINED"
    if status == "stale" or reason == "STALE":
        return "stale", "STALE"
    return "contract-valid", "VALID"


def _result(
    index: int,
    kind: ReportedItemKind,
    outcome: LifecycleOutcome,
    reason: ItemValidationReason,
    source: SourceVersion | None,
) -> ItemValidationResult:
    return ItemValidationResult(
        itemIndex=index,
        kind=kind,
        outcome=outcome,
        reason=reason,
        materializable=outcome == "contract-valid" and reason == "VALID",
        sourceVersionId=source.source_version_id if source else None,
    )


def _reported_kind(value: object) -> ReportedItemKind:
    return cast(ReportedItemKind, value if isinstance(value, str) and value in _KINDS else "unknown")


def _anchor_reason(reason: str) -> ItemValidationReason:
    allowed: set[str] = {
        "SOURCE_MISSING",
        "SOURCE_VERSION_MISMATCH",
        "SOURCE_TAMPERED",
        "SOURCE_STALE",
        "NEGATIVE_OFFSET",
        "REVERSED_RANGE",
        "EMPTY_RANGE",
        "OUT_OF_RANGE",
        "EXACT_QUOTE_MISMATCH",
        "QUOTE_DIGEST_MISMATCH",
        "MISSING_QUOTE",
        "AMBIGUOUS_REPEATED_QUOTE",
        "OCCURRENCE_OUT_OF_RANGE",
        "INVALID_UNICODE",
        "UNSUPPORTED_COORDINATE_VERSION",
        "MAPPING_MISMATCH",
    }
    return cast(ItemValidationReason, reason if reason in allowed else "ANCHOR_INVALID")
