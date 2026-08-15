"""Atomic extraction normalization tests."""

from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.normalize import normalize_extraction
from projecta_api.extraction.service import _ingestion_body


def test_normalization_deduplicates_and_orders_all_candidate_categories() -> None:
    response = ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v1",
            "modelId": "replay",
            "modelVersion": "fixture",
            "entities": [
                {
                    "type": "Requirement",
                    "label": "need",
                    "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"},
                    "confidence": "0.5",
                },
                {
                    "type": "Requirement",
                    "label": "need",
                    "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"},
                    "confidence": "0.9",
                },
            ],
            "relations": [
                {
                    "predicate": "implements",
                    "sourceEntityId": "task-1",
                    "targetEntityId": "req-1",
                    "evidence": {"startOffset": 0, "endOffset": 4, "text": "link"},
                    "confidence": "0.4",
                },
                {
                    "predicate": "implements",
                    "sourceEntityId": "task-1",
                    "targetEntityId": "req-1",
                    "evidence": {"startOffset": 0, "endOffset": 4, "text": "link"},
                    "confidence": "0.8",
                },
            ],
            "links": [
                {
                    "mention": "need",
                    "targetEntityId": "req-1",
                    "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"},
                    "confidence": "0.6",
                },
                {
                    "mention": "need",
                    "targetEntityId": "req-1",
                    "evidence": {"startOffset": 5, "endOffset": 9, "text": "need"},
                    "confidence": "0.7",
                },
            ],
        }
    )

    result = normalize_extraction(
        "link need",
        response,
        [
            {"id": "task-1", "type": "Task", "label": "task"},
            {"id": "req-1", "type": "Requirement", "label": "need"},
        ],
    )

    assert len(result.entities) == 1
    assert len(result.relations) == 1
    assert len(result.links) == 1
    assert result.relations[0].evidence.start_offset == 0


def test_m3_v2_local_candidates_support_relation_end_to_end_without_context() -> None:
    raw_text = "Task implements requirement."
    response = ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v2",
            "modelId": "candidate",
            "modelVersion": "candidate-v1",
            "entities": [
                {
                    "candidateId": "task-1",
                    "type": "Task",
                    "label": "Task",
                    "evidence": {"startOffset": 0, "endOffset": 4, "text": "Task"},
                    "confidence": 0.9,
                },
                {
                    "candidateId": "requirement-1",
                    "type": "Requirement",
                    "label": "requirement",
                    "evidence": {
                        "startOffset": 16,
                        "endOffset": 27,
                        "text": "requirement",
                    },
                    "confidence": 0.9,
                },
            ],
            "relations": [
                {
                    "predicate": "implements",
                    "sourceEntityId": "task-1",
                    "targetEntityId": "requirement-1",
                    "evidence": {
                        "startOffset": 0,
                        "endOffset": 28,
                        "text": raw_text,
                    },
                    "confidence": 0.8,
                }
            ],
            "links": [],
            "abstentionReason": None,
        }
    )

    normalized = normalize_extraction(raw_text, response, [])
    body = _ingestion_body(raw_text, normalized)

    assert normalized.relations[0].source_entity_id == "task-1"
    assert normalized.relations[0].target_entity_id == "requirement-1"
    assert body["entities"][0]["candidateId"] == "task-1"
    assert body["relations"][0]["sourceEntityId"] == "task-1"
