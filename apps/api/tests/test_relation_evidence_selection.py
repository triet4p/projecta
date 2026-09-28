"""RM-59 deterministic source-bound relation evidence selection tests."""

from __future__ import annotations

from typing import cast

from projecta_api.extraction.confirmed_entity_gate import RelationAuthorization
from projecta_api.extraction.relation_evidence_selection import (
    build_source_blocks,
    select_relation_evidence,
    serialize_relation_evidence,
)
from projecta_api.extraction.source_version import SourceVersion, create_source_version
from projecta_api.extraction.text_anchor import resolve_text_anchor


def _authorization(source: SourceVersion) -> RelationAuthorization:
    return RelationAuthorization(
        relationId="rel_" + "1" * 64,
        sourceHandle="eh1_" + "2" * 64,
        targetHandle="eh1_" + "3" * 64,
        predicate="supports",
        sourceVersionId=source.source_version_id,
        idempotentReplay=False,
    )


def _fixture(content: str = "Task supports decision in one clause.") -> tuple[SourceVersion, str, RelationAuthorization]:
    source = create_source_version(
        project_id="project-alpha", source_artifact_id="note-1", content=content
    )
    return source, content, _authorization(source)


def test_selects_smallest_valid_clause_or_sentence_boundary() -> None:
    source, content, authorization = _fixture()
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    trigger_anchor = resolve_text_anchor(source, content, "supports")

    selection = select_relation_evidence(
        "project-alpha",
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
        trigger_anchor=trigger_anchor,
        trigger_required=True,
    )

    assert selection.outcome == "selected"
    assert selection.reason == "SELECTED"
    assert selection.materializable is True
    assert selection.block is not None
    assert selection.block.kind == "sentence"
    assert selection.block.start_offset == 0
    assert selection.block.end_offset == len(content)


def test_cross_sentence_and_missing_required_trigger_abstain() -> None:
    source, content, authorization = _fixture("Task appears. decision appears.")
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")

    cross_sentence = select_relation_evidence(
        "project-alpha", source, content, authorization, source_anchor, target_anchor
    )
    missing_trigger = select_relation_evidence(
        "project-alpha",
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
        trigger_required=True,
    )
    assert (cross_sentence.outcome, cross_sentence.reason) == ("abstained", "NO_COMMON_BOUNDARY")
    assert (missing_trigger.outcome, missing_trigger.reason) == ("abstained", "TRIGGER_MISSING")


def test_optional_trigger_is_allowed_but_supplied_out_of_block_trigger_abstains() -> None:
    source, content, authorization = _fixture("Task supports decision. Other trigger.")
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    optional = select_relation_evidence(
        "project-alpha", source, content, authorization, source_anchor, target_anchor
    )
    outside = resolve_text_anchor(source, content, "trigger")
    with_outside = select_relation_evidence(
        "project-alpha",
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
        trigger_anchor=outside,
    )
    assert optional.outcome == "selected"
    assert (with_outside.outcome, with_outside.reason) == ("abstained", "NO_COMMON_BOUNDARY")


def test_tied_server_blocks_route_to_review_without_first_match_fallback() -> None:
    source, content, authorization = _fixture()
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    block = build_source_blocks(source, content)[0]

    selection = select_relation_evidence(
        "project-alpha",
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
        server_blocks=[block, block],
    )

    assert (selection.outcome, selection.reason) == ("review-required", "TIED_BOUNDARIES")
    assert selection.materializable is False


def test_repeated_unicode_and_newline_mentions_are_explicit_and_idempotent() -> None:
    content = "🚀 Task supports 决定\r\n🚀 Task supports 决定."
    source, _, authorization = _fixture(content)
    source_anchor = resolve_text_anchor(source, content, "Task", occurrence=2)
    target_anchor = resolve_text_anchor(source, content, "决定", occurrence=2)
    trigger_anchor = resolve_text_anchor(source, content, "supports", occurrence=2)

    first = select_relation_evidence(
        "project-alpha",
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
        trigger_anchor=trigger_anchor,
        trigger_required=True,
    )
    second = select_relation_evidence(
        "project-alpha",
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
        trigger_anchor=trigger_anchor,
        trigger_required=True,
    )
    assert first.safe_dict() == second.safe_dict()
    assert first.outcome == "selected"


def test_stale_project_version_endpoint_and_block_tamper_fail_closed() -> None:
    source, content, authorization = _fixture()
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    changed = select_relation_evidence(
        "project-alpha", source, content + " changed", authorization, source_anchor, target_anchor
    )
    assert (changed.outcome, changed.reason) == ("abstained", "SOURCE_STALE")

    project_mismatch = select_relation_evidence(
        "project-beta", source, content, authorization, source_anchor, target_anchor
    )
    assert (project_mismatch.outcome, project_mismatch.reason) == ("quarantined", "PROJECT_MISMATCH")

    mismatch_auth = authorization.model_copy(update={"source_version_id": "sv_" + "0" * 64})
    mismatch = select_relation_evidence(
        "project-alpha", source, content, mismatch_auth, source_anchor, target_anchor
    )
    assert (mismatch.outcome, mismatch.reason) == ("abstained", "SOURCE_VERSION_MISMATCH")

    blocks = build_source_blocks(source, content)
    tampered = blocks[0].model_copy(update={"content_digest": "sha256:" + "0" * 64})
    block_tamper = select_relation_evidence(
        "project-alpha", source, content, authorization, source_anchor, target_anchor, server_blocks=[tampered]
    )
    assert (block_tamper.outcome, block_tamper.reason) == ("quarantined", "SOURCE_TAMPERED")


def test_endpoint_containment_unsupported_predicate_and_safe_serialization() -> None:
    source, content, authorization = _fixture("Task supports decision. Other sentence.")
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    blocks = build_source_blocks(source, content)
    only_other = [block for block in blocks if block.start_offset > 0]
    outside = select_relation_evidence(
        "project-alpha", source, content, authorization, source_anchor, target_anchor, server_blocks=only_other
    )
    assert (outside.outcome, outside.reason) == ("abstained", "NO_COMMON_BOUNDARY")

    unsupported = authorization.model_copy(update={"predicate": "unknownPredicate"})
    unsupported_result = select_relation_evidence(
        "project-alpha", source, content, unsupported, source_anchor, target_anchor
    )
    assert (unsupported_result.outcome, unsupported_result.reason) == ("quarantined", "UNSUPPORTED_PREDICATE")

    selected = select_relation_evidence(
        "project-alpha", source, content, authorization, source_anchor, target_anchor
    )
    serialized = serialize_relation_evidence(selected)
    assert "Task" not in serialized
    assert "decision" not in serialized
    assert "exactQuote" not in serialized


def test_orchestrator_exposes_selection_as_explicit_opt_in() -> None:
    from projecta_api.context import TrustedRequestContext
    from projecta_api.extraction.service import ExtractionOrchestrator, ExtractionPersistence

    source, content, authorization = _fixture()
    source_anchor = resolve_text_anchor(source, content, "Task")
    target_anchor = resolve_text_anchor(source, content, "decision")
    orchestrator = ExtractionOrchestrator(None, cast(ExtractionPersistence, object()), None)
    result = orchestrator.select_relation_evidence(
        TrustedRequestContext("project-alpha", "actor", "request"),
        source,
        content,
        authorization,
        source_anchor,
        target_anchor,
    )
    assert result.outcome == "selected"
