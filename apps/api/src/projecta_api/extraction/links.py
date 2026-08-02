"""Project-scoped entity-link proposal normalization."""

from collections.abc import Sequence

from projecta_api.extraction.contracts import EntityLinkCandidateOutput, ExtractionResponse
from projecta_api.llm.gateway import NormalizedGatewayError


def normalize_entity_link_candidates(
    raw_text: str,
    response: ExtractionResponse,
    bounded_entities: Sequence[dict[str, str]],
) -> list[EntityLinkCandidateOutput]:
    """Keep links only when the target is in the trusted same-project context."""
    allowed_ids = {item.get("id") for item in bounded_entities}
    normalized: list[EntityLinkCandidateOutput] = []
    for candidate in response.links:
        span = candidate.evidence
        if span.end_offset > len(raw_text) or raw_text[span.start_offset : span.end_offset] != span.text:
            raise NormalizedGatewayError("invalid_evidence", "link evidence does not match source text", retryable=False)
        if candidate.target_entity_id not in allowed_ids:
            raise NormalizedGatewayError(
                "hallucinated_link", "entity link target is outside bounded project context", retryable=False
            )
        if candidate.mention != span.text:
            raise NormalizedGatewayError("invalid_evidence", "link mention must equal its evidence text", retryable=False)
        normalized.append(candidate)
    return normalized
