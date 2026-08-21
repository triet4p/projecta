"""Contract tests for Sprint 12 v4 sanitized relation signatures."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_evaluator_sanitized_signatures", ROOT / "scripts/sprint12_evaluator.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


GOLD_ENTITIES = [
    {"id": "gold-source", "type": "Task", "span": {"start": 0, "end": 4}},
    {
        "id": "gold-target",
        "type": "Requirement",
        "span": {"start": 10, "end": 20},
    },
]
PREDICTED_ENTITIES = [
    {
        "candidateId": "pred-source",
        "type": "Task",
        "span": {"startOffset": 0, "endOffset": 4},
    },
    {
        "candidateId": "pred-target",
        "type": "Requirement",
        "span": {"startOffset": 10, "endOffset": 20},
    },
]


def relation_instrumentation(predicted_relation: dict | None) -> dict:
    gold = {
        "entities": GOLD_ENTITIES,
        "relations": [
            {
                "predicate": "implements",
                "sourceEntityId": "gold-source",
                "targetEntityId": "gold-target",
                "span": {"start": 0, "end": 20},
            }
        ],
        "links": [],
        "abstention": {"required": False},
    }
    prediction = {
        "entities": PREDICTED_ENTITIES,
        "relations": [predicted_relation] if predicted_relation else [],
        "links": [],
        "abstention": {"required": False},
    }
    return MODULE.score_extraction(gold, prediction, ["implements"])[
        "relationInstrumentation"
    ]


def test_signature_contains_only_sanitized_relation_fields() -> None:
    instrumentation = relation_instrumentation(
        {
            "predicate": "implements",
            "sourceEntityId": "pred-source",
            "targetEntityId": "pred-target",
            "span": {"startOffset": 1, "endOffset": 19},
        }
    )
    assert instrumentation["version"] == "s12.relation-instrumentation.v4"
    assert instrumentation["reconciliation"]["pass"] is True

    gold_signature = instrumentation["signatures"]["gold"][0]
    predicted_signature = instrumentation["signatures"]["predicted"][0]
    expected_fields = {
        "predicate",
        "sourceEndpoint",
        "targetEndpoint",
        "evidenceSpan",
        "errorClass",
    }
    assert set(gold_signature) == expected_fields
    assert set(predicted_signature) == expected_fields
    assert gold_signature["errorClass"] == "wrongSpan"
    assert predicted_signature["errorClass"] == "wrongSpan"
    assert gold_signature["sourceEndpoint"] == {
        "status": "resolved",
        "startOffset": 0,
        "endOffset": 4,
        "type": "Task",
    }
    assert predicted_signature["targetEndpoint"] == {
        "status": "resolved",
        "startOffset": 10,
        "endOffset": 20,
        "type": "Requirement",
    }
    assert predicted_signature["evidenceSpan"] == {
        "startOffset": 1,
        "endOffset": 19,
    }

    serialized = json.dumps(instrumentation, ensure_ascii=False)
    for forbidden in (
        "gold-source",
        "pred-source",
        "candidateId",
        "entityId",
        "rawText",
        '"text"',
    ):
        assert forbidden not in serialized


def test_missing_and_extra_signatures_keep_error_class_and_reconcile() -> None:
    missing = relation_instrumentation(None)
    assert missing["signatures"]["gold"][0]["errorClass"] == "missingRelation"
    assert missing["signatures"]["predicted"] == []
    assert missing["reconciliation"]["pass"] is True

    extra = relation_instrumentation(
        {
            "predicate": "supports",
            "sourceEntityId": "pred-source",
            "targetEntityId": "missing-target",
            "span": {"startOffset": 2, "endOffset": 8},
        }
    )
    assert extra["signatures"]["gold"][0]["errorClass"] == "missingRelation"
    assert extra["signatures"]["predicted"][0]["errorClass"] == "extraRelation"
    assert extra["signatures"]["predicted"][0]["targetEndpoint"] == {
        "status": "missing"
    }
    assert extra["reconciliation"]["pass"] is True
