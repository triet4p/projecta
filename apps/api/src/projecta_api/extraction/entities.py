"""Deterministic typed entity extraction from structured gateway output."""

from projecta_api.extraction.contracts import EntityCandidateOutput, ExtractionResponse
from projecta_api.llm.gateway import NormalizedGatewayError


def normalize_entity_candidates(
    raw_text: str, response: ExtractionResponse
) -> list[EntityCandidateOutput]:
    """Accept only allowlisted entities whose evidence exactly matches source text."""
    normalized: list[EntityCandidateOutput] = []
    for candidate in response.entities:
        span = candidate.evidence
        if span.end_offset > len(raw_text) or raw_text[span.start_offset : span.end_offset] != span.text:
            raise NormalizedGatewayError(
                "invalid_evidence", "entity evidence does not match source text", retryable=False
            )
        normalized.append(candidate)
    return normalized
