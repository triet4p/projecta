"""RM-58 server-owned confirmed entity and relation gate tests."""

from __future__ import annotations

from typing import cast

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.confirmed_entity_gate import (
    ConfirmedEntityGateError,
    EntityHandle,
    InMemoryConfirmedEntityRegistry,
    RelationRequest,
    serialize_entity_handle,
    serialize_relation_authorization,
)
from projecta_api.extraction.item_validation import ItemValidationResult, validate_item_batch
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence
from projecta_api.extraction.source_version import SourceVersion, create_source_version
from projecta_api.extraction.text_anchor import resolve_text_anchor


def _fixture() -> tuple[SourceVersion, str, ItemValidationResult, InMemoryConfirmedEntityRegistry]:
    content = "The task supports the decision."
    source = create_source_version(
        project_id="project-alpha", source_artifact_id="note-1", content=content
    )
    anchor = resolve_text_anchor(source, content, "task")
    item = {
        "schemaVersion": "item-validation.v1",
        "kind": "entity",
        "projectId": "project-alpha",
        "sourceVersionId": source.source_version_id,
        "anchor": anchor.model_dump(mode="json", by_alias=True),
        "payload": {"type": "Task", "label": "task", "candidateId": "candidate-1"},
    }
    validation = validate_item_batch("project-alpha", source, content, [item]).results[0]
    return source, content, validation, InMemoryConfirmedEntityRegistry()


def _handles() -> tuple[
    SourceVersion,
    str,
    ItemValidationResult,
    InMemoryConfirmedEntityRegistry,
    EntityHandle,
    EntityHandle,
]:
    source, content, validation, registry = _fixture()
    first = registry.issue_entity_handle(
        "project-alpha",
        source,
        validation,
        "Task",
        "candidate-1",
        confirmation_revision="review-1",
    )
    second = registry.issue_entity_handle(
        "project-alpha",
        source,
        validation,
        "Decision",
        "candidate-2",
        confirmation_revision="review-1",
    )
    return source, content, validation, registry, first, second


def _request(
    first: EntityHandle,
    second: EntityHandle,
    *,
    key: str = "request-1",
    **updates: object,
) -> RelationRequest:
    values: dict[str, object] = {
        "sourceHandle": first.handle,
        "targetHandle": second.handle,
        "predicate": "supports",
        "requestKey": key,
    }
    values.update(updates)
    return RelationRequest.model_validate(values)


def test_happy_direction_resolves_both_handles_and_is_safe() -> None:
    source, _, _, registry, first, second = _handles()

    authorization = registry.authorize_relation(
        "project-alpha", source, _request(first, second)
    )

    assert authorization.source_handle == first.handle
    assert authorization.target_handle == second.handle
    assert authorization.predicate == "supports"
    assert authorization.idempotent_replay is False
    assert "candidate-1" not in serialize_entity_handle(first)
    assert "candidate-2" not in serialize_relation_authorization(authorization)
    assert "exactQuote" not in serialize_relation_authorization(authorization)


@pytest.mark.parametrize(
    ("source_handle", "reason"),
    [
        ("candidate-created-by-model", "MODEL_CREATED_ID"),
        ("eh1_bad", "MALFORMED_HANDLE"),
        ("eh1_" + "0" * 64, "UNKNOWN_HANDLE"),
    ],
)
def test_model_global_free_text_malformed_and_unknown_handles_fail_closed(
    source_handle: str, reason: str
) -> None:
    source, _, _, registry, _, second = _handles()
    request = _request(
        EntityHandle.model_construct(handle=source_handle),
        second,
    )

    with pytest.raises(ConfirmedEntityGateError) as failure:
        registry.authorize_relation("project-alpha", source, request)
    assert failure.value.reason == reason


def test_project_isolation_and_source_staleness_are_rejected() -> None:
    source, content, _, registry, first, second = _handles()
    request = _request(first, second)

    with pytest.raises(ConfirmedEntityGateError, match="PROJECT_MISMATCH"):
        registry.authorize_relation("project-beta", source, request)

    changed = create_source_version(
        project_id="project-alpha", source_artifact_id="note-1", content=content + " changed"
    )
    with pytest.raises(ConfirmedEntityGateError, match="SOURCE_VERSION_MISMATCH"):
        registry.authorize_relation("project-alpha", changed, request)


def test_confirmation_revision_and_expected_type_mismatch_are_stale_or_rejected() -> None:
    source, _, _, registry, first, second = _handles()

    with pytest.raises(ConfirmedEntityGateError, match="STALE_CONFIRMATION"):
        registry.authorize_relation(
            "project-alpha",
            source,
            _request(
                first,
                second,
                sourceConfirmationRevision="rev_" + "0" * 64,
            ),
        )
    with pytest.raises(ConfirmedEntityGateError, match="TYPE_VERSION_MISMATCH"):
        registry.authorize_relation(
            "project-alpha", source, _request(first, second, sourceEntityType="Decision")
        )


def test_self_unknown_predicate_and_type_allowlist_fail_closed() -> None:
    source, _, validation, registry, first, second = _handles()
    with pytest.raises(ConfirmedEntityGateError, match="ENTITY_TYPE_NOT_ALLOWLISTED"):
        registry.issue_entity_handle(
            "project-alpha",
            source,
            validation,
            "NotReleased",
            "candidate-3",
            confirmation_revision="review-1",
        )
    with pytest.raises(ConfirmedEntityGateError, match="SELF_RELATION"):
        registry.authorize_relation("project-alpha", source, _request(first, first))
    with pytest.raises(ConfirmedEntityGateError, match="UNKNOWN_PREDICATE"):
        registry.authorize_relation(
            "project-alpha", source, _request(first, second, predicate="globalizes")
        )


def test_same_confirmation_is_idempotent_conflicting_replay_and_duplicate_fail() -> None:
    source, _, _, registry, first, second = _handles()
    request = _request(first, second)

    first_authorization = registry.authorize_relation("project-alpha", source, request)
    replay = registry.authorize_relation("project-alpha", source, request)
    assert replay.relation_id == first_authorization.relation_id
    assert replay.idempotent_replay is True

    with pytest.raises(ConfirmedEntityGateError, match="CONFLICTING_REPLAY"):
        registry.authorize_relation(
            "project-alpha", source, _request(first, second, predicate="blocks")
        )
    with pytest.raises(ConfirmedEntityGateError, match="DUPLICATE_RELATION"):
        registry.authorize_relation(
            "project-alpha", source, _request(first, second, key="request-2")
        )


def test_only_contract_valid_or_review_confirmed_entity_can_receive_a_handle() -> None:
    source, content, _, registry, _, _ = _handles()
    anchor = resolve_text_anchor(source, content, "task")
    review_item = {
        "schemaVersion": "item-validation.v1",
        "kind": "entity",
        "status": "review-pending",
        "projectId": "project-alpha",
        "sourceVersionId": source.source_version_id,
        "anchor": anchor.model_dump(mode="json", by_alias=True),
        "payload": {"type": "Task", "label": "task", "candidateId": "candidate-review"},
    }
    review_validation = validate_item_batch("project-alpha", source, content, [review_item]).results[0]
    review_handle = registry.issue_entity_handle(
        "project-alpha",
        source,
        review_validation,
        "Task",
        "candidate-review",
        confirmation_revision="owner-review-1",
        review_confirmed=True,
    )
    assert review_handle.entity_type == "Task"

    with pytest.raises(ConfirmedEntityGateError, match="UNCONFIRMED_ENTITY"):
        registry.issue_entity_handle(
            "project-alpha",
            source,
            review_validation,
            "Task",
            "candidate-review-2",
            confirmation_revision="owner-review-1",
        )


def test_mixed_confirmation_batch_keeps_valid_entity_independent() -> None:
    source, _, validation, registry, _, _ = _handles()
    invalid = validation.model_copy(update={"materializable": False, "reason": "STALE", "outcome": "stale"})
    with pytest.raises(ConfirmedEntityGateError, match="UNCONFIRMED_ENTITY"):
        registry.issue_entity_handle(
            "project-alpha", source, invalid, "Task", "candidate-stale", confirmation_revision="r1"
        )
    valid_handle = registry.issue_entity_handle(
        "project-alpha", source, validation, "Task", "candidate-valid", confirmation_revision="r1"
    )
    assert valid_handle.handle.startswith("eh1_")


def test_orchestrator_exposes_confirm_and_relation_as_explicit_opt_in() -> None:
    source, _, validation, registry, first, second = _handles()
    orchestrator = ExtractionOrchestrator(None, cast(ExtractionPersistence, object()), None)
    context = TrustedRequestContext("project-alpha", "actor", "request")
    issued = orchestrator.confirm_entity(
        context,
        registry,
        source,
        validation,
        "Task",
        "candidate-orchestrator",
        confirmation_revision="review-orchestrator",
    )
    request = _request(issued, second, key="orchestrator-relation")
    authorization = orchestrator.authorize_relation(context, registry, source, request)
    assert authorization.source_handle == issued.handle
