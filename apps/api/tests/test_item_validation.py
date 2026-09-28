"""RM-57 independent per-item validation and quarantine tests."""

from __future__ import annotations

import json
from typing import cast

import pytest

from projecta_api.context import TrustedRequestContext
from projecta_api.extraction.item_validation import (
    ItemMaterializationError,
    can_materialize,
    require_materializable,
    serialize_item_validation,
    validate_item_batch,
)
from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence
from projecta_api.extraction.source_version import SourceVersion, create_source_version
from projecta_api.extraction.text_anchor import resolve_text_anchor


def _fixture() -> tuple[SourceVersion, str, dict[str, object]]:
    content = "The task works."
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
    return source, content, item


def test_mixed_batch_is_independently_classified_and_preserves_order() -> None:
    source, content, valid = _fixture()
    malformed = {**valid, "kind": "relation", "payload": {"predicate": "blocks"}}
    unknown = {**valid, "kind": "future-kind"}
    stale = {**valid, "sourceVersionId": "sv_" + "0" * 64}
    review = {**valid, "status": "review-pending"}
    link = {
        **valid,
        "kind": "entity-link",
        "payload": {"mention": "task", "targetEntityId": "candidate-1"},
    }

    batch = validate_item_batch("project-alpha", source, content, [valid, malformed, unknown, stale, review, link])

    assert [result.item_index for result in batch.results] == [0, 1, 2, 3, 4, 5]
    assert [result.outcome for result in batch.results] == [
        "contract-valid",
        "quarantined",
        "quarantined",
        "stale",
        "review-pending",
        "contract-valid",
    ]
    assert [result.reason for result in batch.results] == [
        "VALID",
        "MALFORMED_ITEM",
        "UNKNOWN_KIND",
        "SOURCE_VERSION_MISMATCH",
        "REVIEW_REQUIRED",
        "VALID",
    ]
    assert [result.materializable for result in batch.results] == [True, False, False, False, False, True]


def test_unknown_status_reason_schema_and_malformed_items_fail_closed() -> None:
    source, content, valid = _fixture()
    cases = [
        ({**valid, "status": "future-status"}, "UNKNOWN_STATUS"),
        ({**valid, "reason": "future-reason"}, "UNKNOWN_REASON"),
        ({**valid, "unexpected": "field"}, "UNKNOWN_SCHEMA_FIELD"),
        ({**valid, "schemaVersion": "item-validation.v9"}, "UNSUPPORTED_SCHEMA_VERSION"),
        ("not-an-item", "MALFORMED_ITEM"),
    ]

    batch = validate_item_batch(
        "project-alpha", source, content, [case[0] for case in cases]
    )

    assert [result.reason for result in batch.results] == [case[1] for case in cases]
    assert all(result.outcome == "quarantined" for result in batch.results)
    assert all(not result.materializable for result in batch.results)


def test_project_source_anchor_and_stale_content_fail_without_contaminating_valid_item() -> None:
    source, content, valid = _fixture()
    project_mismatch = {**valid, "projectId": "project-other"}
    anchor_mismatch = {**valid, "sourceVersionId": source.source_version_id[:-1] + "0"}
    stale_anchor = {**valid}

    batch = validate_item_batch(
        "project-alpha", source, "changed content", [valid, project_mismatch]
    )
    assert batch.results[0].reason == "SOURCE_STALE"
    assert batch.results[0].outcome == "stale"
    assert batch.results[1].reason == "PROJECT_MISMATCH"
    assert batch.results[1].outcome == "quarantined"

    mismatch_batch = validate_item_batch(
        "project-alpha", source, content, [anchor_mismatch, stale_anchor]
    )
    assert mismatch_batch.results[0].reason == "SOURCE_VERSION_MISMATCH"
    assert mismatch_batch.results[0].outcome == "stale"
    assert mismatch_batch.results[1].reason == "VALID"


def test_evidence_anchor_missing_or_invalid_is_quarantined_independently() -> None:
    source, content, valid = _fixture()
    missing = {**valid, "kind": "evidence", "payload": {}, "anchor": None}
    invalid = {**valid, "kind": "evidence", "payload": {}, "anchor": {"bad": True}}

    batch = validate_item_batch("project-alpha", source, content, [missing, invalid])

    assert [result.reason for result in batch.results] == ["ANCHOR_MISSING", "ANCHOR_INVALID"]
    assert all(result.outcome == "quarantined" for result in batch.results)


def test_serialization_is_deterministic_and_contains_no_raw_payload_or_quote() -> None:
    source, content, valid = _fixture()
    batch = validate_item_batch("project-alpha", source, content, [valid])

    first = serialize_item_validation(batch)
    second = serialize_item_validation(batch)

    assert first == second
    assert "The task works" not in first
    assert "task" not in first
    assert "exactQuote" not in first
    assert list(json.loads(first)) == sorted(json.loads(first))


def test_materialization_guard_rejects_every_non_valid_lifecycle() -> None:
    source, content, valid = _fixture()
    batch = validate_item_batch(
        "project-alpha",
        source,
        content,
        [
            valid,
            {**valid, "status": "review-pending"},
            {**valid, "status": "abstained"},
            {**valid, "status": "quarantined"},
            {**valid, "status": "stale"},
        ],
    )

    assert can_materialize(batch.results[0])
    require_materializable(batch.results[0])
    for result in batch.results[1:]:
        assert not can_materialize(result)
        with pytest.raises(ItemMaterializationError):
            require_materializable(result)


def test_orchestrator_exposes_validation_only_as_explicit_opt_in() -> None:
    source, content, valid = _fixture()
    orchestrator = ExtractionOrchestrator(None, cast(ExtractionPersistence, object()), None)
    batch = orchestrator.validate_items(
        TrustedRequestContext("project-alpha", "actor", "request"),
        source,
        content,
        [valid],
    )

    assert batch.results[0].materializable is True
