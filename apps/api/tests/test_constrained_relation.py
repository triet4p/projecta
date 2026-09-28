"""RM-60 constrained relation contract tests."""

from __future__ import annotations

import hashlib
import json
from typing import cast

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.confirmed_entity_gate import EntityHandle, RelationAuthorization
from projecta_api.extraction.constrained_relation import (
    ConstrainedRelationRequest,
    constrain_relation,
    serialize_constrained_relation,
)
from projecta_api.extraction.relation_evidence_selection import select_relation_evidence
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence
from projecta_api.extraction.source_version import SourceVersion, create_source_version
from projecta_api.extraction.text_anchor import resolve_text_anchor


def _fixture() -> tuple[SourceVersion, str, EntityHandle, EntityHandle, RelationAuthorization]:
    content = "private Task supports decision."
    source = create_source_version(
        project_id="project-alpha", source_artifact_id="note-1", content=content
    )
    source_handle = EntityHandle(
        handle="eh1_" + "1" * 64,
        projectScopeId=source.project_scope_id,
        sourceVersionId=source.source_version_id,
        entityType="Task",
        confirmationRevision="rev_" + "2" * 64,
    )
    target_handle = EntityHandle(
        handle="eh1_" + "3" * 64,
        projectScopeId=source.project_scope_id,
        sourceVersionId=source.source_version_id,
        entityType="Decision",
        confirmationRevision="rev_" + "4" * 64,
    )
    authorization = RelationAuthorization(
        relationId="rel_" + "5" * 64,
        sourceHandle=source_handle.handle,
        targetHandle=target_handle.handle,
        predicate="supports",
        sourceVersionId=source.source_version_id,
        idempotentReplay=False,
    )
    return source, content, source_handle, target_handle, authorization


def _request(
    source: SourceVersion,
    content: str,
    source_handle: EntityHandle,
    target_handle: EntityHandle,
    authorization: RelationAuthorization,
    **updates: object,
) -> ConstrainedRelationRequest:
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    evidence = select_relation_evidence(
        "project-alpha", source, content, authorization, source_anchor, target_anchor
    )
    evidence_digest = "sha256:" + hashlib.sha256(
        json.dumps(evidence.safe_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    values: dict[str, object] = {
        "contractVersion": "constrained-relation.v1",
        "ontologyVersion": "ontology.v0.5.1",
        "authorization": authorization,
        "sourceHandle": source_handle,
        "targetHandle": target_handle,
        "evidence": evidence,
        "evidenceStatus": "selected",
        "evidenceDigest": evidence_digest,
        "polarity": "positive",
        "modality": "asserted",
        "temporal": {"kind": "during", "value": "2026-Q3"},
    }
    values.update(updates)
    return ConstrainedRelationRequest.model_validate(values)


def test_supported_direction_and_selected_evidence_become_review_pending_only() -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    result = constrain_relation(
        "project-alpha", source, _request(source, content, source_handle, target_handle, authorization)
    )

    assert result.outcome == "review-pending"
    assert result.reason == "REVIEW_PENDING"
    assert result.materializable is False
    assert result.evidence_status == "selected"
    assert result.temporal_kind == "during"


@pytest.mark.parametrize(
    ("predicate", "source_type", "target_type", "reason"),
    [
        ("implements", "Task", "Requirement", "REVIEW_PENDING"),
        ("constrainedBy", "Task", "Constraint", "REVIEW_PENDING"),
        ("implements", "Task", "Risk", "UNSUPPORTED_DIRECTION"),
        ("unknownPredicate", "Task", "Decision", "UNSUPPORTED_PREDICATE"),
    ],
)
def test_predicate_type_direction_matrix_is_allowlisted(
    predicate: str, source_type: str, target_type: str, reason: str
) -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    source_handle = source_handle.model_copy(update={"entity_type": source_type})
    target_handle = target_handle.model_copy(update={"entity_type": target_type})
    authorization = authorization.model_copy(update={"predicate": predicate})
    result = constrain_relation(
        "project-alpha", source, _request(source, content, source_handle, target_handle, authorization)
    )
    assert result.reason == reason
    assert result.outcome == ("review-pending" if reason == "REVIEW_PENDING" else "abstained")


@pytest.mark.parametrize("polarity", ["positive", "negative"])
@pytest.mark.parametrize("modality", ["asserted", "possible", "planned", "conditional"])
def test_supported_polarity_and_modality_are_review_pending(
    polarity: str, modality: str
) -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    result = constrain_relation(
        "project-alpha",
        source,
        _request(
            source,
            content,
            source_handle,
            target_handle,
            authorization,
            polarity=polarity,
            modality=modality,
        ),
    )
    assert (result.outcome, result.reason) == ("review-pending", "REVIEW_PENDING")


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("polarity", "unknown", "AMBIGUOUS_POLARITY"),
        ("polarity", "maybe", "UNSUPPORTED_POLARITY"),
        ("modality", "unknown", "AMBIGUOUS_MODALITY"),
        ("modality", "speculative", "UNSUPPORTED_MODALITY"),
    ],
)
def test_ambiguous_or_unknown_semantics_never_assert(
    field: str, value: str, reason: str
) -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    result = constrain_relation(
        "project-alpha",
        source,
        _request(source, content, source_handle, target_handle, authorization, **{field: value}),
    )
    assert result.outcome == "abstained"
    assert result.reason == reason
    assert result.materializable is False


def test_temporal_qualifiers_and_ambiguity_are_fail_closed() -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    valid = constrain_relation(
        "project-alpha",
        source,
        _request(
            source, content, source_handle, target_handle, authorization, temporal={"kind": "before", "value": "2027-01-01"}
        ),
    )
    ambiguous = constrain_relation(
        "project-alpha",
        source,
        _request(
            source, content, source_handle, target_handle, authorization, temporal={"kind": "before", "value": "2027", "ambiguous": True}
        ),
    )
    unsupported = constrain_relation(
        "project-alpha",
        source,
        _request(source, content, source_handle, target_handle, authorization, temporal={"kind": "sometime", "value": "2027"}),
    )
    assert valid.reason == "REVIEW_PENDING"
    assert ambiguous.reason == "AMBIGUOUS_TEMPORAL"
    assert unsupported.reason == "UNSUPPORTED_TEMPORAL"


def test_evidence_status_digest_and_scope_mismatches_never_materialize() -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    base = _request(source, content, source_handle, target_handle, authorization)
    invalid_status = constrain_relation(
        "project-alpha", source, base.model_copy(update={"evidence_status": "review-required"})
    )
    invalid_digest = constrain_relation(
        "project-alpha", source, base.model_copy(update={"evidence_digest": "sha256:" + "0" * 64})
    )
    mismatch = constrain_relation(
        "project-beta", source, base
    )
    stale_auth = authorization.model_copy(update={"source_version_id": "sv_" + "0" * 64})
    stale = constrain_relation(
        "project-alpha", source, base.model_copy(update={"authorization": stale_auth})
    )
    assert invalid_status.reason == "EVIDENCE_STATUS_INVALID"
    assert invalid_digest.reason == "EVIDENCE_DIGEST_MISMATCH"
    assert mismatch.reason == "PROJECT_MISMATCH"
    assert stale.reason == "SOURCE_VERSION_MISMATCH"
    assert all(not result.materializable for result in [invalid_status, invalid_digest, mismatch, stale])


def test_unknown_versions_handles_self_relation_and_deterministic_safe_replay() -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    base = _request(source, content, source_handle, target_handle, authorization)
    unknown_version = base.model_copy(update={"ontology_version": "ontology.v9"})
    self_request = base.model_copy(update={"target_handle": source_handle})
    first = constrain_relation("project-alpha", source, base)
    second = constrain_relation("project-alpha", source, base)
    serialized = serialize_constrained_relation(first)
    assert constrain_relation("project-alpha", source, unknown_version).reason == "UNKNOWN_CONTRACT_VERSION"
    assert constrain_relation("project-alpha", source, self_request).reason == "SELF_RELATION"
    assert first.safe_dict() == second.safe_dict()
    assert "private" not in serialized
    assert source_handle.handle not in serialized
    assert target_handle.handle not in serialized
    assert "exactQuote" not in serialized


def test_orchestrator_exposes_constrained_relation_as_explicit_opt_in() -> None:
    source, content, source_handle, target_handle, authorization = _fixture()
    orchestrator = ExtractionOrchestrator(None, cast(ExtractionPersistence, object()), None)
    result = orchestrator.constrain_relation(
        TrustedRequestContext("project-alpha", "actor", "request"),
        source,
        _request(source, content, source_handle, target_handle, authorization),
    )
    assert result.outcome == "review-pending"
