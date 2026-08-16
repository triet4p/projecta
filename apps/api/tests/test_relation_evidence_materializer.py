"""Deterministic server-owned relation-evidence materializer tests."""

from projecta_api.extraction.contracts import EvidenceSpan
from projecta_api.extraction.relation_evidence import (
    RelationEvidenceRequest,
    materialize_relation_evidence,
)


def span(text: str, value: str, occurrence: int = 0) -> EvidenceSpan:
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(value, start + 1)
    return EvidenceSpan.model_validate({"startOffset": start, "endOffset": start + len(value), "text": value})


def request(text: str, source: str, target: str, trigger: str | None = None) -> RelationEvidenceRequest:
    return RelationEvidenceRequest(
        predicate="implements",
        source_entity_id="task-1",
        target_entity_id="req-1",
        source_span=span(text, source),
        target_span=span(text, target),
        trigger_quote=trigger,
    )


def test_materializer_selects_smallest_clause_with_trigger() -> None:
    text = "The replay job implements the ledger mapping, while the dashboard follows later."
    evidence = materialize_relation_evidence(text, request(text, "replay job", "ledger mapping", "implements"))

    assert evidence is not None
    assert evidence.text == "The replay job implements the ledger mapping"


def test_materializer_uses_endpoint_offsets_for_repeated_mentions() -> None:
    text = "The old task blocks review. The new task implements the review requirement."
    relation = RelationEvidenceRequest(
        predicate="implements",
        source_entity_id="task-new",
        target_entity_id="req-1",
        source_span=span(text, "new task"),
        target_span=span(text, "review requirement"),
        trigger_quote="implements",
    )

    evidence = materialize_relation_evidence(text, relation)

    assert evidence is not None
    assert evidence.text == "The new task implements the review requirement."


def test_materializer_supports_unicode_sentence_boundaries_and_fails_closed() -> None:
    text = "担当者 🚦 が承認します。次の作業は保留です。"
    relation = RelationEvidenceRequest(
        predicate="supports",
        source_entity_id="actor-1",
        target_entity_id="decision-1",
        source_span=span(text, "担当者 🚦"),
        target_span=span(text, "承認"),
        trigger_quote="承認",
    )
    evidence = materialize_relation_evidence(text, relation)
    missing_trigger = materialize_relation_evidence(text, request(text, "担当者 🚦", "承認", "does-not-exist"))

    assert evidence is not None
    assert evidence.text == "担当者 🚦 が承認します。"
    assert missing_trigger is None


def test_materializer_selects_the_requested_pair_among_multiple_entities() -> None:
    text = "Task A implements Req A; Task B supports Req B."
    relation = RelationEvidenceRequest(
        predicate="supports",
        source_entity_id="task-b",
        target_entity_id="req-b",
        source_span=span(text, "Task B"),
        target_span=span(text, "Req B"),
        trigger_quote="supports",
    )

    evidence = materialize_relation_evidence(text, relation)

    assert evidence is not None
    assert evidence.text == "Task B supports Req B."


def test_materializer_fails_closed_for_invalid_spans_and_separate_sentences() -> None:
    text = "Task implements requirement. Review follows later."
    invalid = RelationEvidenceRequest(
        predicate="implements",
        source_entity_id="task-1",
        target_entity_id="req-1",
        source_span=EvidenceSpan.model_validate({"startOffset": 0, "endOffset": 4, "text": "Nope"}),
        target_span=span(text, "requirement"),
        trigger_quote="implements",
    )
    separate = RelationEvidenceRequest(
        predicate="implements",
        source_entity_id="task-1",
        target_entity_id="req-1",
        source_span=span(text, "Task"),
        target_span=span(text, "Review"),
        trigger_quote="implements",
    )

    assert materialize_relation_evidence(text, invalid) is None
    assert materialize_relation_evidence(text, separate) is None


def test_materializer_fails_closed_when_required_trigger_is_missing() -> None:
    text = "Task implements requirement."
    relation = RelationEvidenceRequest(
        predicate="implements",
        source_entity_id="task-1",
        target_entity_id="req-1",
        source_span=span(text, "Task"),
        target_span=span(text, "requirement"),
        trigger_required=True,
    )

    assert materialize_relation_evidence(text, relation) is None
