"""Fixtures for mutually exclusive Sprint 12 relation diagnostics."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_evaluator_relation_v3", ROOT / "scripts/sprint12_evaluator.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


ENTITIES = {
    "gold": [
        {"id": "gold-source", "type": "Task", "span": {"start": 0, "end": 4}},
        {
            "id": "gold-target",
            "type": "Requirement",
            "span": {"start": 10, "end": 20},
        },
    ],
    "prediction": [
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
        {
            "candidateId": "pred-other",
            "type": "Requirement",
            "span": {"startOffset": 22, "endOffset": 28},
        },
    ],
}


def score(predicted_relation: dict | None) -> dict:
    gold = {
        "entities": ENTITIES["gold"],
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
        "entities": ENTITIES["prediction"],
        "relations": [predicted_relation] if predicted_relation else [],
        "links": [],
        "abstention": {"required": False},
    }
    return MODULE.score_extraction(gold, prediction, ["implements", "supports"])[
        "relationInstrumentation"
    ]


@pytest.mark.parametrize(
    ("relation", "bucket"),
    [
        (
            {
                "predicate": "implements",
                "sourceEntityId": "pred-source",
                "targetEntityId": "pred-target",
                "span": {"startOffset": 0, "endOffset": 20},
            },
            "exactMatch",
        ),
        (
            {
                "predicate": "implements",
                "sourceEntityId": "pred-source",
                "targetEntityId": "pred-target",
                "span": {"startOffset": 1, "endOffset": 19},
            },
            "wrongSpan",
        ),
        (
            {
                "predicate": "supports",
                "sourceEntityId": "pred-source",
                "targetEntityId": "pred-target",
                "span": {"startOffset": 0, "endOffset": 20},
            },
            "wrongPredicate",
        ),
        (
            {
                "predicate": "implements",
                "sourceEntityId": "pred-target",
                "targetEntityId": "pred-source",
                "span": {"startOffset": 0, "endOffset": 20},
            },
            "reversedEndpoint",
        ),
        (
            {
                "predicate": "implements",
                "sourceEntityId": "pred-source",
                "targetEntityId": "pred-other",
                "span": {"startOffset": 0, "endOffset": 20},
            },
            "correctPredicateWrongEndpoint",
        ),
    ],
)
def test_each_relation_confusion_has_one_exclusive_bucket(
    relation: dict, bucket: str
) -> None:
    instrumentation = score(relation)
    assert instrumentation["version"] == "s12.relation-instrumentation.v4"
    assert instrumentation["reconciliation"]["pass"] is True
    assert instrumentation["totals"][bucket] == 1
    assert sum(
        instrumentation["totals"][name]
        for name in (
            "exactMatch",
            "wrongSpan",
            "wrongPredicate",
            "reversedEndpoint",
            "missingEndpoint",
            "correctPredicateWrongEndpoint",
            "missingRelation",
            "extraRelation",
        )
    ) == 1


def test_missing_and_extra_relations_reconcile_separately() -> None:
    missing = score(None)
    assert missing["totals"]["missingRelation"] == 1
    assert missing["totals"]["extraRelation"] == 0
    assert missing["reconciliation"]["pass"] is True

    extra = score(
        {
            "predicate": "supports",
            "sourceEntityId": "pred-source",
            "targetEntityId": "pred-other",
            "span": {"startOffset": 2, "endOffset": 8},
        }
    )
    assert extra["totals"]["missingRelation"] == 1
    assert extra["totals"]["extraRelation"] == 1
    assert extra["reconciliation"]["pass"] is True


def test_instrumentation_is_sanitized_and_exposes_reconciliation() -> None:
    serialized = json.dumps(score(None), ensure_ascii=False)
    assert "gold-source" not in serialized
    assert "pred-source" not in serialized
    assert "rawText" not in serialized
    assert '"goldCategorized": 1' in serialized
    assert '"predictedCategorized": 0' in serialized
