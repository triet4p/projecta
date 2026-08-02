"""Bounded entity-link proposal tests."""

import pytest

from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.links import normalize_entity_link_candidates
from projecta_api.llm.gateway import NormalizedGatewayError


def _response(target: str) -> ExtractionResponse:
    return ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v1",
            "modelId": "replay",
            "modelVersion": "fixture",
            "entities": [],
            "relations": [],
            "links": [
                {
                    "mention": "checkout team",
                    "targetEntityId": target,
                    "evidence": {"startOffset": 13, "endOffset": 26, "text": "checkout team"},
                    "confidence": "0.8",
                }
            ],
        }
    )


def test_link_is_retained_only_for_bounded_same_project_target() -> None:
    result = normalize_entity_link_candidates(
        "Le asked the checkout team.", _response("team-1"), [{"id": "team-1", "type": "Person", "label": "team"}]
    )

    assert result[0].target_entity_id == "team-1"


def test_fabricated_or_cross_project_target_fails_closed() -> None:
    with pytest.raises(NormalizedGatewayError) as caught:
        normalize_entity_link_candidates("Le asked the checkout team.", _response("other-team"), [{"id": "team-1", "type": "Person", "label": "team"}])

    assert caught.value.retryable is False


def test_no_link_output_is_an_explicit_abstention_path() -> None:
    response = ExtractionResponse.model_validate(
        {"schemaVersion": "m3.v1", "modelId": "replay", "modelVersion": "fixture", "entities": [], "relations": [], "links": [], "abstentionReason": "ambiguous"}
    )

    assert normalize_entity_link_candidates("No clear owner.", response, []) == []
