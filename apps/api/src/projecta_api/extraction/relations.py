"""Allowlisted relation candidate normalization."""

from collections.abc import Collection

from projecta_api.extraction.contracts import ExtractionResponse, RelationCandidateOutput
from projecta_api.llm.gateway import NormalizedGatewayError


def normalize_relation_candidates(
    raw_text: str,
    response: ExtractionResponse,
    valid_entity_ids: Collection[str],
) -> list[RelationCandidateOutput]:
    """Accept only approved predicates between valid same-project endpoints."""
    allowed = set(valid_entity_ids)
    normalized: list[RelationCandidateOutput] = []
    for candidate in response.relations:
        span = candidate.evidence
        if span.end_offset > len(raw_text) or raw_text[span.start_offset : span.end_offset] != span.text:
            raise NormalizedGatewayError("invalid_evidence", "relation evidence does not match source text", retryable=False)
        if candidate.source_entity_id not in allowed or candidate.target_entity_id not in allowed:
            raise NormalizedGatewayError(
                "cross_project_link", "relation endpoint is outside the trusted project", retryable=False
            )
        if candidate.source_entity_id == candidate.target_entity_id:
            raise NormalizedGatewayError("normalization_invalid", "self-relation is not allowed", retryable=False)
        normalized.append(candidate)
    return normalized
