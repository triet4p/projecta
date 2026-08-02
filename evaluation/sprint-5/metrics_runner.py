"""Executable Sprint 5 quality metrics for replay and live outputs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[2] / "apps" / "api" / "src"))

from projecta_api.extraction.contracts import ExtractionResponse


def evaluate(cases: list[dict[str, Any]], responses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    schema_valid = 0
    category = {name: {"tp": 0, "expected": 0, "observed": 0} for name in ("entities", "relations", "links")}
    exact_spans = {"matched": 0, "expected": 0}
    abstention = {"tp": 0, "expected": 0, "observed": 0}
    cross_project_rejections = 0
    for case in cases:
        _validate_gold_spans(case)
        actual = responses.get(case["id"], {})
        if not _schema_valid(actual):
            continue
        schema_valid += 1
        gold = case.get("gold", {})
        for name, values in category.items():
            expected = {_candidate_key(item, name) for item in gold.get(name, [])}
            observed = {_candidate_key(item, name) for item in actual.get(name, [])}
            values["tp"] += len(expected & observed)
            values["expected"] += len(expected)
            values["observed"] += len(observed)
            for item in gold.get(name, []):
                exact_spans["expected"] += 1
                if any(
                    _span_key(item) == _span_key(value)
                    and _evidence_matches_source(case["rawText"], value)
                    for value in actual.get(name, [])
                ):
                    exact_spans["matched"] += 1
        needs = bool(gold.get("abstentionReason"))
        got = bool(actual.get("abstentionReason"))
        abstention["tp"] += int(needs and got)
        abstention["expected"] += int(needs)
        abstention["observed"] += int(got)
        if case.get("slice") == "negative.cross-project" and got:
            cross_project_rejections += 1

    metrics: dict[str, Any] = {"schemaValidity": _ratio(schema_valid, len(cases))}
    for name, values in category.items():
        metrics[f"{name}Precision"] = _ratio(values["tp"], values["observed"])
        metrics[f"{name}Recall"] = _ratio(values["tp"], values["expected"])
        metrics[f"{name}F1"] = _f1(metrics[f"{name}Precision"], metrics[f"{name}Recall"])
    metrics["exactSpanScore"] = _ratio(exact_spans["matched"], exact_spans["expected"])
    metrics["abstentionPrecision"] = _ratio(abstention["tp"], abstention["observed"])
    metrics["abstentionRecall"] = _ratio(abstention["tp"], abstention["expected"])
    metrics["crossProjectRejection"] = _ratio(cross_project_rejections, sum(case.get("slice") == "negative.cross-project" for case in cases))
    metrics["calibration"] = None
    metrics["latencyMs"] = {"p50": None, "p95": None}
    metrics["cost"] = {"inputTokens": 0, "outputTokens": 0}
    thresholds = {
        "schemaValidity": 1.0,
        "entitiesF1": 0.85,
        "relationsF1": 0.85,
        "linksF1": 0.85,
        "exactSpanScore": 1.0,
        "crossProjectRejection": 1.0,
        "abstentionPrecision": 1.0,
        "abstentionRecall": 0.9,
    }
    failures = {name: {"actual": metrics[name], "required": value} for name, value in thresholds.items() if (metrics[name] or 0) < value}
    return {"metrics": metrics, "thresholds": thresholds, "failures": failures, "status": "passed" if not failures else "failed"}


def _candidate_key(item: dict[str, Any], category: str) -> tuple[Any, ...]:
    if category == "entities":
        return item.get("type"), _span_key(item)
    if category == "relations":
        return item.get("predicate"), item.get("sourceEntityId"), item.get("targetEntityId"), _span_key(item)
    return item.get("mention"), item.get("targetEntityId"), _span_key(item)


def _schema_valid(value: dict[str, Any]) -> bool:
    try:
        ExtractionResponse.model_validate(value)
    except Exception:  # noqa: BLE001 - invalid model output is a reported metric
        return False
    return True


def _span_key(item: dict[str, Any]) -> tuple[Any, ...]:
    evidence = item.get("evidence", item)
    return evidence.get("startOffset"), evidence.get("endOffset")


def _evidence_matches_source(raw_text: str, item: dict[str, Any]) -> bool:
    evidence = item.get("evidence", item)
    start = evidence.get("startOffset")
    end = evidence.get("endOffset")
    text = evidence.get("text")
    return (
        isinstance(start, int)
        and isinstance(end, int)
        and isinstance(text, str)
        and 0 <= start < end <= len(raw_text)
        and raw_text[start:end] == text
    )


def _validate_gold_spans(case: dict[str, Any]) -> None:
    raw_text = case["rawText"]
    for category in ("entities", "relations", "links"):
        for item in case.get("gold", {}).get(category, []):
            start, end = _span_key(item)
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or not 0 <= start < end <= len(raw_text)
            ):
                raise ValueError(
                    f"invalid gold span in {case['id']}: {category} [{start}, {end})"
                )


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0
