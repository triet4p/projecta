"""Typed entity extraction and Unicode evidence tests."""

import pytest

from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.entities import normalize_entity_candidates
from projecta_api.llm.gateway import NormalizedGatewayError


def _response(span_text: str, start: int, end: int) -> ExtractionResponse:
    return ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v1",
            "modelId": "replay",
            "modelVersion": "fixture",
            "entities": [
                {
                    "type": "Task",
                    "label": span_text,
                    "evidence": {"startOffset": start, "endOffset": end, "text": span_text},
                    "confidence": "0.8",
                }
            ],
            "relations": [],
            "links": [],
        }
    )


def test_entity_extraction_recomputes_unicode_code_point_evidence() -> None:
    raw = "🚀 Le sẽ kiểm tra API thuế."

    result = normalize_entity_candidates(raw, _response("kiểm tra API thuế", 8, 25))

    assert result[0].evidence.text == raw[8:25]


def test_entity_extraction_rejects_mismatched_evidence_before_persistence() -> None:
    with pytest.raises(NormalizedGatewayError) as caught:
        normalize_entity_candidates("Confirm address", _response("wrong", 0, 7))

    assert caught.value.error_class == "invalid_evidence"
