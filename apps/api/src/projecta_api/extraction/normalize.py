"""Atomic normalization pipeline used before any Semantic Core mutation."""

from collections.abc import Callable, Sequence

from projecta_api.extraction.contracts import (
    EntityCandidateOutput,
    EntityLinkCandidateOutput,
    ExtractionResponse,
    RelationCandidateOutput,
)
from projecta_api.extraction.entities import normalize_entity_candidates
from projecta_api.extraction.links import normalize_entity_link_candidates
from projecta_api.extraction.relations import normalize_relation_candidates


def normalize_extraction(
    raw_text: str,
    response: ExtractionResponse,
    bounded_entities: list[dict[str, str]],
) -> ExtractionResponse:
    """Validate all categories first, then canonicalize duplicates and ordering."""
    valid_ids = [item["id"] for item in bounded_entities]
    valid_ids.extend(
        candidate.candidate_id
        for candidate in response.entities
        if candidate.candidate_id is not None
    )
    entities = normalize_entity_candidates(raw_text, response)
    relations = normalize_relation_candidates(raw_text, response, valid_ids)
    links = normalize_entity_link_candidates(raw_text, response, bounded_entities)

    return response.model_copy(
        update={
            "entities": _unique_sorted(entities, _entity_key),
            "relations": _unique_sorted(relations, _relation_key),
            "links": _unique_sorted(links, _link_key),
        }
    )


def _unique_sorted[T](values: Sequence[T], key: Callable[[T], tuple[object, ...]]) -> list[T]:
    unique = {key(value): value for value in values}
    return [unique[item] for item in sorted(unique)]


def _entity_key(value: EntityCandidateOutput) -> tuple[object, ...]:
    return (value.evidence.start_offset, value.evidence.end_offset, value.type, value.label)


def _relation_key(value: RelationCandidateOutput) -> tuple[object, ...]:
    return (
        value.evidence.start_offset,
        value.evidence.end_offset,
        value.predicate,
        value.source_entity_id,
        value.target_entity_id,
    )


def _link_key(value: EntityLinkCandidateOutput) -> tuple[object, ...]:
    return (
        value.evidence.start_offset,
        value.evidence.end_offset,
        value.target_entity_id,
        value.mention,
    )
