"""Deterministic, server-owned materialization of relation evidence."""

from __future__ import annotations

from dataclasses import dataclass

from projecta_api.extraction.contracts import EvidenceSpan, RelationPredicate

_SENTENCE_TERMINATORS = frozenset(".!?。！？\n")
_CLAUSE_SEPARATORS = frozenset(",;:，；：")
TRIGGER_REQUIRED_PREDICATES = frozenset(
    {
        "implements",
        "blocks",
        "dependsOn",
        "supports",
        "answers",
        "resolves",
        "constrainedBy",
    }
)


@dataclass(frozen=True, slots=True)
class RelationEvidenceRequest:
    """Canonical relation data supplied by the extraction server."""

    predicate: RelationPredicate
    source_entity_id: str
    target_entity_id: str
    source_span: EvidenceSpan
    target_span: EvidenceSpan
    trigger_quote: str | None = None
    trigger_required: bool = False


def materialize_relation_evidence(
    raw_text: str, request: RelationEvidenceRequest
) -> EvidenceSpan | None:
    """Return the smallest unambiguous clause/sentence containing the relation.

    The function is deliberately fail-closed. It never invents offsets, joins
    separate sentences, or chooses between equally small ambiguous spans.
    """

    if not request.predicate or request.source_entity_id == request.target_entity_id:
        return None
    if not _valid_span(raw_text, request.source_span) or not _valid_span(raw_text, request.target_span):
        return None
    if request.source_span.start_offset == request.target_span.start_offset:
        return None
    if request.trigger_quote == "":
        return None
    if request.trigger_required and request.trigger_quote is None:
        return None

    sentence_ranges = _ranges(raw_text, _SENTENCE_TERMINATORS)
    candidates: list[tuple[int, int]] = []
    for sentence_start, sentence_end in sentence_ranges:
        if not _contains(sentence_start, sentence_end, request.source_span, request.target_span):
            continue
        trigger_ranges = _trigger_ranges(raw_text, request.trigger_quote, sentence_start, sentence_end)
        if request.trigger_quote is not None and not trigger_ranges:
            continue
        for clause_start, clause_end in _clause_ranges(raw_text[sentence_start:sentence_end]):
            clause_start += sentence_start
            clause_end += sentence_start
            if not _contains(clause_start, clause_end, request.source_span, request.target_span):
                continue
            if request.trigger_quote is None or any(
                clause_start <= trigger_start and trigger_end <= clause_end
                for trigger_start, trigger_end in trigger_ranges
            ):
                candidates.append((_trim_left(raw_text, clause_start, clause_end), _trim_right(raw_text, clause_start, clause_end)))
        # A required trigger is a clause-level contract.  Falling back to the
        # whole sentence here would accept a trigger that is merely adjacent
        # to the endpoint clause and would make the contract depend on
        # sentence punctuation.  Legacy, trigger-free materialization keeps
        # its sentence fallback for compatibility.
        if not candidates and request.trigger_quote is None:
            candidates.append((_trim_left(raw_text, sentence_start, sentence_end), _trim_right(raw_text, sentence_start, sentence_end)))

    unique = sorted(set(candidates), key=lambda item: (item[1] - item[0], item[0], item[1]))
    if not unique or (len(unique) > 1 and (unique[0][1] - unique[0][0]) == (unique[1][1] - unique[1][0])):
        return None
    start, end = unique[0]
    return EvidenceSpan.model_validate({"startOffset": start, "endOffset": end, "text": raw_text[start:end]})


def _valid_span(raw_text: str, span: EvidenceSpan) -> bool:
    return (
        0 <= span.start_offset < span.end_offset <= len(raw_text)
        and raw_text[span.start_offset : span.end_offset] == span.text
    )


def _contains(start: int, end: int, *spans: EvidenceSpan) -> bool:
    return all(start <= span.start_offset and span.end_offset <= end for span in spans)


def _trigger_ranges(raw_text: str, trigger: str | None, start: int, end: int) -> list[tuple[int, int]]:
    if trigger is None:
        return []
    ranges: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        found = raw_text.find(trigger, cursor, end)
        if found < 0:
            break
        ranges.append((found, found + len(trigger)))
        cursor = found + max(1, len(trigger))
    return ranges


def _ranges(text: str, terminators: frozenset[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for index, character in enumerate(text):
        if character in terminators:
            ranges.append((start, index + 1))
            start = index + 1
    if start < len(text):
        ranges.append((start, len(text)))
    return ranges


def _clause_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start = 0
    for index, character in enumerate(text):
        if character in _CLAUSE_SEPARATORS:
            if start < index:
                ranges.append((start, index))
            start = index + 1
    if start < len(text):
        ranges.append((start, len(text)))
    return ranges


def _trim_left(raw_text: str, start: int, end: int) -> int:
    while start < end and raw_text[start].isspace():
        start += 1
    return start


def _trim_right(raw_text: str, start: int, end: int) -> int:
    while end > start and raw_text[end - 1].isspace():
        end -= 1
    return end
