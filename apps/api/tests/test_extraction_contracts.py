"""Contract tests for strict provider-neutral M3 extraction output."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from projecta_api.extraction.contracts import ExtractionResponse


def _response(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schemaVersion": "m3.v1",
        "modelId": "replay",
        "modelVersion": "fixture-1",
        "entities": [
            {
                "type": "Requirement",
                "label": "address confirmation",
                "evidence": {"startOffset": 0, "endOffset": 19, "text": "address confirmation"},
                "confidence": "0.90",
            }
        ],
        "relations": [],
        "links": [],
    }
    value.update(overrides)
    return value


def test_contract_accepts_allowlisted_candidate_and_aliases() -> None:
    result = ExtractionResponse.model_validate(_response())

    assert result.schema_version == "m3.v1"
    assert result.entities[0].confidence == Decimal("0.90")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("type", "ArbitraryRdfClass"),
        ("predicate", "https://example.invalid/predicate"),
        ("targetEntityId", "https://example.invalid/entity"),
    ],
)
def test_contract_rejects_untrusted_vocabulary_or_iri(field: str, value: str) -> None:
    if field == "type":
        candidate = {"type": value, "label": "x", "evidence": {"startOffset": 0, "endOffset": 1, "text": "x"}, "confidence": 0.5}
        payload = _response(entities=[candidate])
    elif field == "predicate":
        candidate = {"predicate": value, "sourceEntityId": "a", "targetEntityId": "b", "evidence": {"startOffset": 0, "endOffset": 1, "text": "x"}, "confidence": 0.5}
        payload = _response(relations=[candidate])
    else:
        candidate = {"mention": "x", "targetEntityId": value, "evidence": {"startOffset": 0, "endOffset": 1, "text": "x"}, "confidence": 0.5}
        payload = _response(links=[candidate])

    with pytest.raises(ValidationError):
        ExtractionResponse.model_validate(payload)


def test_contract_rejects_abstention_with_candidates_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ExtractionResponse.model_validate(_response(abstentionReason="ambiguous"))

    with pytest.raises(ValidationError):
        ExtractionResponse.model_validate(_response(providerPayload={"secret": "redacted"}))


def test_contract_accepts_explicit_empty_abstention() -> None:
    result = ExtractionResponse.model_validate(
        _response(entities=[], relations=[], links=[], abstentionReason="insufficient evidence")
    )

    assert result.abstention_reason == "insufficient evidence"
