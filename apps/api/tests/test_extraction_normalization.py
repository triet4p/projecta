"""Atomic extraction normalization tests."""

from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.normalize import normalize_extraction


def test_normalization_deduplicates_and_orders_all_candidate_categories() -> None:
    response = ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v1",
            "modelId": "replay",
            "modelVersion": "fixture",
            "entities": [
                {"type": "Requirement", "label": "need", "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"}, "confidence": "0.5"},
                {"type": "Requirement", "label": "need", "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"}, "confidence": "0.9"}
            ],
            "relations": [
                {"predicate": "implements", "sourceEntityId": "task-1", "targetEntityId": "req-1", "evidence": {"startOffset": 0, "endOffset": 4, "text": "link"}, "confidence": "0.4"},
                {"predicate": "implements", "sourceEntityId": "task-1", "targetEntityId": "req-1", "evidence": {"startOffset": 0, "endOffset": 4, "text": "link"}, "confidence": "0.8"}
            ],
            "links": [
                {"mention": "need", "targetEntityId": "req-1", "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"}, "confidence": "0.6"},
                {"mention": "need", "targetEntityId": "req-1", "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"}, "confidence": "0.7"}
            ]
        }
    )

    result = normalize_extraction(
        "link need",
        response,
        [{"id": "task-1", "type": "Task", "label": "task"}, {"id": "req-1", "type": "Requirement", "label": "need"}],
    )

    assert len(result.entities) == 1
    assert len(result.relations) == 1
    assert len(result.links) == 1
    assert result.relations[0].evidence.start_offset == 0
