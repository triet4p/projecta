"""Regression coverage for the versioned trigger-aware relation envelope."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from projecta_api.extraction.relation_evidence_envelope import (
    RelationEvidenceEnvelopeV1,
    materialize_relation_evidence_envelope,
)


def _extraction() -> dict:
    return {
        "schemaVersion": "m3.v2",
        "modelId": "deepseek-v4-flash",
        "modelVersion": "test",
        "entities": [
            {
                "candidateId": "source-1",
                "type": "Task",
                "label": "source",
                "evidence": {"startOffset": 0, "endOffset": 6, "text": "source"},
                "confidence": Decimal("0.9"),
            },
            {
                "candidateId": "target-1",
                "type": "Decision",
                "label": "target",
                "evidence": {"startOffset": 16, "endOffset": 22, "text": "target"},
                "confidence": Decimal("0.9"),
            },
        ],
        "relations": [
            {
                "predicate": "supports",
                "sourceEntityId": "source-1",
                "targetEntityId": "target-1",
                "evidence": {"startOffset": 0, "endOffset": 22, "text": "source supports target"},
                "confidence": Decimal("0.8"),
            }
        ],
    }


def test_trigger_aware_envelope_accepts_one_binding_per_relation() -> None:
    envelope = RelationEvidenceEnvelopeV1.model_validate(
        {
            "schemaVersion": "relation-evidence-envelope.v1",
            "extraction": _extraction(),
            "relationTriggers": [
                {
                    "predicate": "supports",
                    "sourceEntityId": "source-1",
                    "targetEntityId": "target-1",
                    "triggerQuote": "supports",
                }
            ],
        }
    )
    assert envelope.schema_version == "relation-evidence-envelope.v1"
    assert envelope.relation_triggers[0].trigger_quote == "supports"


def test_trigger_aware_envelope_fails_closed_when_trigger_is_missing() -> None:
    with pytest.raises(ValidationError, match="requires one triggerQuote"):
        RelationEvidenceEnvelopeV1.model_validate(
            {
                "schemaVersion": "relation-evidence-envelope.v1",
                "extraction": _extraction(),
                "relationTriggers": [],
            }
        )


def test_materializer_uses_trigger_quote_and_drops_out_of_context_quote() -> None:
    valid = RelationEvidenceEnvelopeV1.model_validate(
        {
            "schemaVersion": "relation-evidence-envelope.v1",
            "extraction": _extraction(),
            "relationTriggers": [
                {
                    "predicate": "supports",
                    "sourceEntityId": "source-1",
                    "targetEntityId": "target-1",
                    "triggerQuote": "supports",
                }
            ],
        }
    )
    scored = materialize_relation_evidence_envelope("source supports target", valid)
    assert scored is not None
    assert len(scored.relations) == 1
    assert scored.relations[0].evidence.text == "source supports target"

    invalid = valid.model_copy(
        update={
            "relation_triggers": [
                valid.relation_triggers[0].model_copy(
                    update={"trigger_quote": "not-present"}
                )
            ]
        }
    )
    dropped = materialize_relation_evidence_envelope("source supports target", invalid)
    assert dropped is not None
    assert dropped.relations == []
