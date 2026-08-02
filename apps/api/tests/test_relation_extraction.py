"""Relation predicate, endpoint, and evidence tests."""

import pytest

from projecta_api.extraction.contracts import ExtractionResponse
from projecta_api.extraction.relations import normalize_relation_candidates
from projecta_api.llm.gateway import NormalizedGatewayError


def _response(source: str = "task-1", target: str = "req-1") -> ExtractionResponse:
    return ExtractionResponse.model_validate(
        {
            "schemaVersion": "m3.v1",
            "modelId": "replay",
            "modelVersion": "fixture",
            "entities": [],
            "relations": [
                {
                    "predicate": "implements",
                    "sourceEntityId": source,
                    "targetEntityId": target,
                    "evidence": {"startOffset": 0, "endOffset": 15, "text": "task implements"},
                    "confidence": "0.7",
                }
            ],
            "links": [],
        }
    )


def test_relation_requires_allowlisted_same_project_endpoints() -> None:
    result = normalize_relation_candidates("task implements requirement", _response(), ["task-1", "req-1"])

    assert result[0].predicate == "implements"


def test_relation_rejects_unknown_endpoint_and_self_relation() -> None:
    with pytest.raises(NormalizedGatewayError) as unknown:
        normalize_relation_candidates("task implements requirement", _response(target="other"), ["task-1", "req-1"])
    assert unknown.value.error_class == "cross_project_link"

    with pytest.raises(NormalizedGatewayError) as self_relation:
        normalize_relation_candidates("task implements requirement", _response(target="task-1"), ["task-1"])
    assert self_relation.value.error_class == "normalization_invalid"
