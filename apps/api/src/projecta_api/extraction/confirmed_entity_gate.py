"""Server-owned confirmed-entity handles and a project/source relation gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.extraction.contracts import RelationPredicate
from projecta_api.extraction.item_validation import ItemValidationResult
from projecta_api.extraction.source_version import SourceVersion

CONFIRMED_ENTITY_CONTRACT_VERSION: Final = "entity-handle.v1"
RELATION_GATE_CONTRACT_VERSION: Final = "relation-gate.v1"

ReleasedEntityType = Literal[
    "Requirement",
    "Decision",
    "Question",
    "Task",
    "Risk",
    "Assumption",
    "Constraint",
    "ProgressClaim",
    "ResearchFinding",
]
GateFailureReason = Literal[
    "SOURCE_MISSING",
    "PROJECT_MISMATCH",
    "SOURCE_VERSION_MISMATCH",
    "SOURCE_TAMPERED",
    "MALFORMED_HANDLE",
    "MODEL_CREATED_ID",
    "UNKNOWN_HANDLE",
    "UNCONFIRMED_ENTITY",
    "STALE_CONFIRMATION",
    "ENTITY_TYPE_NOT_ALLOWLISTED",
    "TYPE_VERSION_MISMATCH",
    "SELF_RELATION",
    "UNKNOWN_PREDICATE",
    "DUPLICATE_RELATION",
    "CONFLICTING_REPLAY",
    "MALFORMED_REQUEST",
]

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
_PREDICATES: frozenset[str] = frozenset(
    {"implements", "blocks", "dependsOn", "supports", "answers", "resolves", "constrainedBy"}
)
_OPAQUE_KEY = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_HANDLE_PREFIX = "eh1_"


class ConfirmedEntityGateError(ValueError):
    """Raised when a handle or relation cannot be authorized fail-closed."""

    def __init__(self, reason: GateFailureReason) -> None:
        self.reason = reason
        super().__init__(reason)


class EntityHandle(BaseModel):
    """Safe server-issued handle; candidate keys never cross this boundary."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["entity-handle.v1"] = Field(
        default=CONFIRMED_ENTITY_CONTRACT_VERSION, alias="contractVersion"
    )
    handle: str = Field(pattern=r"^eh1_[0-9a-f]{64}$")
    project_scope_id: str = Field(alias="projectScopeId", pattern=r"^project_[0-9a-f]{64}$")
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    entity_type: ReleasedEntityType = Field(alias="entityType")
    confirmation_revision: str = Field(
        alias="confirmationRevision", pattern=r"^rev_[0-9a-f]{64}$"
    )

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


class RelationRequest(BaseModel):
    """Relation gate input containing handles, never global or free-text IDs."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["relation-gate.v1"] = Field(
        default=RELATION_GATE_CONTRACT_VERSION, alias="contractVersion"
    )
    source_handle: str = Field(alias="sourceHandle")
    target_handle: str = Field(alias="targetHandle")
    predicate: str
    source_entity_type: str | None = Field(default=None, alias="sourceEntityType")
    target_entity_type: str | None = Field(default=None, alias="targetEntityType")
    source_confirmation_revision: str | None = Field(
        default=None, alias="sourceConfirmationRevision", pattern=r"^rev_[0-9a-f]{64}$"
    )
    target_confirmation_revision: str | None = Field(
        default=None, alias="targetConfirmationRevision", pattern=r"^rev_[0-9a-f]{64}$"
    )
    request_key: str = Field(alias="requestKey", pattern=_OPAQUE_KEY)

class RelationAuthorization(BaseModel):
    """Safe relation authorization returned only after both handles resolve."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["relation-gate.v1"] = Field(
        default=RELATION_GATE_CONTRACT_VERSION, alias="contractVersion"
    )
    relation_id: str = Field(alias="relationId", pattern=r"^rel_[0-9a-f]{64}$")
    source_handle: str = Field(alias="sourceHandle", pattern=r"^eh1_[0-9a-f]{64}$")
    target_handle: str = Field(alias="targetHandle", pattern=r"^eh1_[0-9a-f]{64}$")
    predicate: RelationPredicate
    source_version_id: str = Field(alias="sourceVersionId", pattern=r"^sv_[0-9a-f]{64}$")
    idempotent_replay: bool = Field(alias="idempotentReplay")

    def safe_dict(self) -> dict[str, object]:
        return cast(dict[str, object], self.model_dump(mode="json", by_alias=True))


class ConfirmedEntityRegistry(Protocol):
    """Port for persistence-backed handle registries; this task supplies memory only."""

    def issue_entity_handle(
        self,
        project_id: str,
        source: SourceVersion | None,
        validation: ItemValidationResult,
        entity_type: str,
        candidate_key: str,
        *,
        confirmation_revision: str,
        review_confirmed: bool = False,
    ) -> EntityHandle: ...

    def authorize_relation(
        self, project_id: str, source: SourceVersion | None, request: RelationRequest
    ) -> RelationAuthorization: ...


@dataclass
class _EntityRecord:
    project_id: str
    candidate_key: str
    handle: EntityHandle
    current: bool = True


class InMemoryConfirmedEntityRegistry:
    """Deterministic vertical-slice registry without bypassing persistence ports."""

    def __init__(self) -> None:
        self._entities: dict[str, _EntityRecord] = {}
        self._current_by_candidate: dict[str, str] = {}
        self._relations_by_request: dict[str, tuple[str, RelationAuthorization]] = {}
        self._relations_by_pair: set[tuple[str, str, str]] = set()

    def issue_entity_handle(
        self,
        project_id: str,
        source: SourceVersion | None,
        validation: ItemValidationResult,
        entity_type: str,
        candidate_key: str,
        *,
        confirmation_revision: str,
        review_confirmed: bool = False,
    ) -> EntityHandle:
        source = self._require_source(project_id, source)
        if validation.kind != "entity" or (
            not validation.materializable
            and not (validation.outcome == "review-pending" and review_confirmed)
        ):
            raise ConfirmedEntityGateError("UNCONFIRMED_ENTITY")
        if entity_type not in _ENTITY_TYPES:
            raise ConfirmedEntityGateError("ENTITY_TYPE_NOT_ALLOWLISTED")
        if not _is_opaque(candidate_key) or not _is_opaque(confirmation_revision):
            raise ConfirmedEntityGateError("MALFORMED_REQUEST")
        if validation.source_version_id != source.source_version_id:
            raise ConfirmedEntityGateError("SOURCE_VERSION_MISMATCH")
        revision = _revision_id(project_id, source.source_version_id, candidate_key, confirmation_revision)
        candidate_fingerprint = _candidate_fingerprint(project_id, candidate_key, entity_type)
        current_handle_id = self._current_by_candidate.get(candidate_fingerprint)
        if current_handle_id:
            current = self._entities[current_handle_id]
            if (
                current.handle.source_version_id == source.source_version_id
                and current.handle.confirmation_revision == revision
            ):
                return current.handle
            current.current = False
        handle = EntityHandle(
            handle=_handle_id(project_id, source.source_version_id, candidate_key, entity_type, revision),
            projectScopeId=source.project_scope_id,
            sourceVersionId=source.source_version_id,
            entityType=cast(ReleasedEntityType, entity_type),
            confirmationRevision=revision,
        )
        self._entities[handle.handle] = _EntityRecord(project_id, candidate_key, handle)
        self._current_by_candidate[candidate_fingerprint] = handle.handle
        return handle

    def resolve_entity_handle(
        self,
        project_id: str,
        source: SourceVersion | None,
        value: str,
        *,
        expected_type: str | None = None,
        expected_revision: str | None = None,
    ) -> EntityHandle:
        source = self._require_source(project_id, source)
        if not isinstance(value, str) or not value.startswith(_HANDLE_PREFIX):
            if isinstance(value, str) and value.startswith("eh"):
                raise ConfirmedEntityGateError("TYPE_VERSION_MISMATCH")
            raise ConfirmedEntityGateError("MODEL_CREATED_ID")
        if len(value) != len(_HANDLE_PREFIX) + 64 or any(
            character not in "0123456789abcdef" for character in value[len(_HANDLE_PREFIX) :]
        ):
            raise ConfirmedEntityGateError("MALFORMED_HANDLE")
        record = self._entities.get(value)
        if record is None:
            raise ConfirmedEntityGateError("UNKNOWN_HANDLE")
        if record.project_id != project_id or record.handle.project_scope_id != source.project_scope_id:
            raise ConfirmedEntityGateError("PROJECT_MISMATCH")
        if record.handle.source_version_id != source.source_version_id:
            raise ConfirmedEntityGateError("SOURCE_VERSION_MISMATCH")
        if not record.current:
            raise ConfirmedEntityGateError("STALE_CONFIRMATION")
        if expected_type is not None and expected_type != record.handle.entity_type:
            raise ConfirmedEntityGateError("TYPE_VERSION_MISMATCH")
        if expected_revision is not None and expected_revision != record.handle.confirmation_revision:
            raise ConfirmedEntityGateError("STALE_CONFIRMATION")
        return record.handle

    def authorize_relation(
        self, project_id: str, source: SourceVersion | None, request: RelationRequest
    ) -> RelationAuthorization:
        source = self._require_source(project_id, source)
        if request.predicate not in _PREDICATES:
            raise ConfirmedEntityGateError("UNKNOWN_PREDICATE")
        if request.source_handle == request.target_handle:
            raise ConfirmedEntityGateError("SELF_RELATION")
        source_handle = self.resolve_entity_handle(
            project_id,
            source,
            request.source_handle,
            expected_type=request.source_entity_type,
            expected_revision=request.source_confirmation_revision,
        )
        target_handle = self.resolve_entity_handle(
            project_id,
            source,
            request.target_handle,
            expected_type=request.target_entity_type,
            expected_revision=request.target_confirmation_revision,
        )
        pair_key = (source_handle.handle, target_handle.handle, request.predicate)
        request_fingerprint = _stable_json(
            {
                "projectScopeId": source.project_scope_id,
                "sourceHandle": source_handle.handle,
                "targetHandle": target_handle.handle,
                "predicate": request.predicate,
            }
        ).decode("utf-8")
        prior = self._relations_by_request.get(request.request_key)
        if prior is not None:
            prior_fingerprint, authorization = prior
            if prior_fingerprint != request_fingerprint:
                raise ConfirmedEntityGateError("CONFLICTING_REPLAY")
            return authorization.model_copy(update={"idempotent_replay": True})
        if pair_key in self._relations_by_pair:
            raise ConfirmedEntityGateError("DUPLICATE_RELATION")
        relation = RelationAuthorization(
            relationId=_relation_id(request_fingerprint),
            sourceHandle=source_handle.handle,
            targetHandle=target_handle.handle,
            predicate=cast(RelationPredicate, request.predicate),
            sourceVersionId=source.source_version_id,
            idempotentReplay=False,
        )
        self._relations_by_request[request.request_key] = (request_fingerprint, relation)
        self._relations_by_pair.add(pair_key)
        return relation

    def _require_source(self, project_id: str, source: SourceVersion | None) -> SourceVersion:
        if source is None:
            raise ConfirmedEntityGateError("SOURCE_MISSING")
        if source.project_id != project_id:
            raise ConfirmedEntityGateError("PROJECT_MISMATCH")
        return source


def serialize_entity_handle(handle: EntityHandle) -> str:
    return _stable_json(handle.safe_dict()).decode("utf-8")


def serialize_relation_authorization(authorization: RelationAuthorization) -> str:
    return _stable_json(authorization.safe_dict()).decode("utf-8")


def _candidate_fingerprint(project_id: str, candidate_key: str, entity_type: str) -> str:
    return _digest(_stable_json({"project": project_id, "candidate": candidate_key, "type": entity_type}))


def _revision_id(project_id: str, source_version_id: str, candidate_key: str, revision: str) -> str:
    return "rev_" + _digest(
        _stable_json(
            {
                "project": project_id,
                "sourceVersionId": source_version_id,
                "candidate": candidate_key,
                "revision": revision,
            }
        )
    )


def _handle_id(
    project_id: str, source_version_id: str, candidate_key: str, entity_type: str, revision: str
) -> str:
    return _HANDLE_PREFIX + _digest(
        _stable_json(
            {
                "project": project_id,
                "sourceVersionId": source_version_id,
                "candidate": candidate_key,
                "type": entity_type,
                "revision": revision,
            }
        )
    )


def _relation_id(fingerprint: str) -> str:
    return "rel_" + _digest(fingerprint.encode("utf-8"))


def _is_opaque(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    import re

    return re.fullmatch(_OPAQUE_KEY, value) is not None


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _stable_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8", "strict"
    )
