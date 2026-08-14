#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Deterministic Sprint 12 Phase E evaluation harness.

The harness is deliberately independent from a model runtime. It validates the
versioned fixture, scores supplied model outputs, and fails closed when a live
baseline configuration is not available. Reports contain identifiers and
digests only; source text is never copied into evidence artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
JsonObject: TypeAlias = dict[str, JSONValue]
JsonList: TypeAlias = list[JSONValue]
EVALUATOR_VERSION = "s12.evaluator.v1"
REQUIRED_RUNTIME_ENV = (
    "PROJECTA_LLM_TYPE",
    "PROJECTA_LLM_BASE_URL",
    "PROJECTA_LLM_API_KEY",
    "PROJECTA_LLM_MODEL",
)


class EvaluationError(ValueError):
    """Raised when an evaluation input violates a declared contract."""


@dataclass(frozen=True)
class LoadedDataset:
    """Validated dataset and its version-bound manifest."""

    dataset: JsonObject
    manifest: JsonObject
    cases: tuple[JsonObject, ...]
    scenarios: tuple[JsonObject, ...]


def _object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise EvaluationError(f"malformed {label}: expected object")
    return cast(JsonObject, value)


def _list(value: object, label: str) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise EvaluationError(f"malformed {label}: expected object list")
    return [cast(JsonObject, item) for item in value]


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationError(f"missing or invalid {label}")
    return value


def _canonical(value: JSONValue) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: JSONValue) -> str:
    """Return a stable sha256 digest for a JSON value."""

    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def read_json(path: Path) -> JsonObject:
    """Read a JSON object without accepting malformed top-level values."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot read JSON {path}: {exc}") from exc
    return _object(value, str(path))


def _require_keys(
    value: Mapping[str, JSONValue], keys: Iterable[str], label: str
) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise EvaluationError(f"{label} missing required fields: {', '.join(missing)}")


def _validate_source(case: JsonObject) -> None:
    source = _object(case.get("source"), f"{case.get('caseId', 'case')}.source")
    _require_keys(
        source,
        (
            "rawText",
            "language",
            "origin",
            "sensitivity",
            "license",
            "permissionRef",
            "contentDigest",
        ),
        "source",
    )
    raw_text = _string(source.get("rawText"), "source.rawText")
    expected = "sha256:" + hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    if source.get("contentDigest") != expected:
        raise EvaluationError(f"tampered source digest for {case.get('caseId')}")
    for name in ("origin", "sensitivity", "license", "permissionRef"):
        _string(source.get(name), f"source.{name}")


def _validate_case(
    case: JsonObject, allowed_splits: set[str], allow_test: bool
) -> None:
    case_id = _string(case.get("caseId"), "caseId")
    if case.get("schemaVersion") != "s12.atomic.v1":
        raise EvaluationError(f"unknown schema for {case_id}")
    _require_keys(
        case,
        ("caseId", "schemaVersion", "journeyId", "source", "split", "gold"),
        case_id,
    )
    split = _string(case.get("split"), f"{case_id}.split")
    if split not in {"development", "validation", "test"}:
        raise EvaluationError(f"invalid split for {case_id}: {split}")
    if split == "test" and not allow_test:
        raise EvaluationError(f"test split is sealed: {case_id}")
    if split not in allowed_splits:
        raise EvaluationError(f"split-policy violation for {case_id}: {split}")
    _validate_source(case)
    gold = _object(case.get("gold"), f"{case_id}.gold")
    _require_keys(
        gold,
        ("entities", "relations", "links", "abstention", "semanticGaps"),
        f"{case_id}.gold",
    )


def _validate_manifest(manifest: JsonObject) -> dict[str, JsonObject]:
    entries = _list(manifest.get("atomicCases"), "manifest.atomicCases")
    by_id: dict[str, JsonObject] = {}
    content_digests: dict[str, str] = {}
    for entry in entries:
        case_id = _string(entry.get("caseId"), "manifest.caseId")
        if case_id in by_id:
            raise EvaluationError(f"duplicate manifest ID: {case_id}")
        case_digest = _string(entry.get("caseDigest"), f"{case_id}.caseDigest")
        content_digest = _string(entry.get("contentDigest"), f"{case_id}.contentDigest")
        if (
            content_digest in content_digests
            and content_digests[content_digest] != case_id
        ):
            raise EvaluationError(f"cross-split duplicate content digest: {case_id}")
        by_id[case_id] = entry
        content_digests[content_digest] = case_id
        if not case_digest.startswith("sha256:") or len(case_digest) != 71:
            raise EvaluationError(f"invalid case digest: {case_id}")
    return by_id


def _validate_scenario(
    scenario: JsonObject,
    atomic_ids: set[str],
    allowed_splits: set[str],
    allow_test: bool,
) -> None:
    scenario_id = _string(scenario.get("scenarioId"), "scenarioId")
    if scenario.get("schemaVersion") != "s12.scenario.v1":
        raise EvaluationError(f"unknown scenario schema for {scenario_id}")
    _require_keys(
        scenario,
        (
            "scenarioId",
            "schemaVersion",
            "journeyId",
            "split",
            "events",
            "checkpoints",
            "competencyAnswers",
            "sourceManifest",
        ),
        scenario_id,
    )
    split = _string(scenario.get("split"), f"{scenario_id}.split")
    if split == "test" and not allow_test:
        raise EvaluationError(f"test split is sealed: {scenario_id}")
    if split not in allowed_splits:
        raise EvaluationError(f"split-policy violation for {scenario_id}: {split}")
    source_manifest = scenario.get("sourceManifest")
    if not isinstance(source_manifest, list) or not source_manifest:
        raise EvaluationError(f"missing sourceManifest for {scenario_id}")
    if len(set(source_manifest)) != len(source_manifest) or not all(
        item in atomic_ids for item in source_manifest
    ):
        raise EvaluationError(f"invalid scenario references for {scenario_id}")
    events = _list(scenario.get("events"), f"{scenario_id}.events")
    event_ids: set[str] = set()
    for event in events:
        event_id = _string(event.get("eventId"), "eventId")
        if event_id in event_ids or event.get("caseId") not in source_manifest:
            raise EvaluationError(f"invalid event reference for {scenario_id}")
        event_ids.add(event_id)
    for checkpoint in _list(scenario.get("checkpoints"), f"{scenario_id}.checkpoints"):
        for source_id in checkpoint.get("sourceIds", []):
            if source_id not in source_manifest:
                raise EvaluationError(f"invalid checkpoint reference for {scenario_id}")


def load_dataset(
    atomic_path: Path,
    scenario_path: Path,
    manifest_path: Path,
    *,
    allowed_splits: Sequence[str] = ("development", "validation"),
    allow_test: bool = False,
) -> LoadedDataset:
    """Load and validate atomic/scenario payloads against the frozen manifest."""

    allowed = set(allowed_splits)
    dataset = read_json(atomic_path)
    scenario_dataset = read_json(scenario_path)
    manifest = read_json(manifest_path)
    cases = tuple(_list(dataset.get("cases"), "dataset.cases"))
    scenarios = tuple(
        _list(scenario_dataset.get("scenarios"), "scenario_dataset.scenarios")
    )
    manifest_by_id = _validate_manifest(manifest)
    seen: set[str] = set()
    for case in cases:
        case_id = _string(case.get("caseId"), "caseId")
        if case_id in seen:
            raise EvaluationError(f"duplicate payload ID: {case_id}")
        seen.add(case_id)
        _validate_case(case, allowed, allow_test)
        entry = manifest_by_id.get(case_id)
        if entry is None:
            raise EvaluationError(f"payload case absent from manifest: {case_id}")
        if entry.get("contentDigest") != _object(case["source"], "source").get(
            "contentDigest"
        ):
            raise EvaluationError(f"manifest content digest mismatch: {case_id}")
        if entry.get("split") != case.get("split"):
            raise EvaluationError(f"manifest split mismatch: {case_id}")
        if entry.get("caseDigest") != digest(case):
            raise EvaluationError(f"manifest case digest mismatch: {case_id}")
    atomic_ids = set(manifest_by_id)
    scenario_ids: set[str] = set()
    for scenario in scenarios:
        scenario_id = _string(scenario.get("scenarioId"), "scenarioId")
        if scenario_id in scenario_ids:
            raise EvaluationError(f"duplicate scenario ID: {scenario_id}")
        scenario_ids.add(scenario_id)
        _validate_scenario(scenario, atomic_ids, allowed, allow_test)
    return LoadedDataset(dataset, manifest, cases, scenarios)


def _items(value: object) -> list[JsonObject]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _span_signature(item: JsonObject) -> tuple[object, object, object]:
    span = _object(item.get("span"), "span")
    return (
        span.get("start"),
        span.get("end"),
        item.get("type", item.get("targetEntityId", item.get("predicate"))),
    )


def _f1(gold: set[object], predicted: set[object]) -> dict[str, float | int]:
    true_positive = len(gold & predicted)
    if not gold and not predicted:
        return {
            "truePositive": 0,
            "gold": 0,
            "predicted": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        }
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(gold) if gold else (1.0 if not predicted else 0.0)
    value = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "truePositive": true_positive,
        "gold": len(gold),
        "predicted": len(predicted),
        "precision": precision,
        "recall": recall,
        "f1": value,
    }


def score_extraction(gold: JsonObject, prediction: JsonObject | None) -> JsonObject:
    """Score atomic extraction and abstention without silently accepting missing output."""

    if prediction is None:
        return {
            "status": "missing-output",
            "abstentionAccuracy": 0.0,
            "hallucinationRate": 0.0,
            "calibration": {"status": "not-available"},
        }
    result: JsonObject = {}
    for name in ("entities", "relations", "links"):
        expected = {_span_signature(item) for item in _items(gold.get(name))}
        actual = {_span_signature(item) for item in _items(prediction.get(name))}
        result[name] = _f1(expected, actual)
    gold_abstention = (
        _object(gold.get("abstention"), "gold.abstention").get("required") is True
    )
    actual_abstention = (
        _object(prediction.get("abstention"), "prediction.abstention").get("required")
        is True
    )
    result["abstentionAccuracy"] = 1.0 if gold_abstention == actual_abstention else 0.0
    gold_count = sum(
        len(_items(gold.get(name))) for name in ("entities", "relations", "links")
    )
    predicted_count = sum(
        len(_items(prediction.get(name))) for name in ("entities", "relations", "links")
    )
    matched = sum(
        cast(dict[str, int], result[name])["truePositive"]
        for name in ("entities", "relations", "links")
    )
    result["hallucinationRate"] = (
        max(predicted_count - matched, 0) / predicted_count if predicted_count else 0.0
    )
    confidences = prediction.get("confidence")
    if isinstance(confidences, list) and confidences:
        values = [
            float(value) for value in confidences if isinstance(value, (int, float))
        ]
        result["calibration"] = calibration(
            values, [1.0 if actual_abstention == gold_abstention else 0.0] * len(values)
        )
    else:
        result["calibration"] = {"status": "not-available"}
    result["status"] = "scored"
    result["goldItemCount"] = gold_count
    return result


def calibration(
    confidences: Sequence[float], outcomes: Sequence[float], bins: int = 10
) -> JsonObject:
    """Compute Brier score and expected calibration error for bounded confidences."""

    if len(confidences) != len(outcomes) or not confidences:
        return {"status": "not-available"}
    pairs = [
        (min(max(float(c), 0.0), 1.0), float(o))
        for c, o in zip(confidences, outcomes, strict=True)
    ]
    brier = statistics.fmean(
        (confidence - outcome) ** 2 for confidence, outcome in pairs
    )
    bucket_errors: list[float] = []
    for index in range(bins):
        bucket = [
            (confidence, outcome)
            for confidence, outcome in pairs
            if min(int(confidence * bins), bins - 1) == index
        ]
        if bucket:
            bucket_errors.append(
                abs(
                    statistics.fmean(c for c, _ in bucket)
                    - statistics.fmean(o for _, o in bucket)
                )
                * len(bucket)
                / len(pairs)
            )
    return {
        "status": "scored",
        "brier": brier,
        "ece": sum(bucket_errors),
        "count": len(pairs),
    }


def score_ontology_mapping(
    gold: JsonObject, prediction: JsonObject | None
) -> JsonObject:
    """Score released-term mappings, semantic gaps, and policy checks."""

    if prediction is None:
        return {"status": "missing-output"}
    expected = {
        json.dumps(item, sort_keys=True) for item in _items(gold.get("mappings"))
    }
    actual = {
        json.dumps(item, sort_keys=True) for item in _items(prediction.get("mappings"))
    }
    expected_gaps = {
        str(item.get("label")) for item in _items(gold.get("semanticGaps"))
    }
    actual_gaps = {
        str(item.get("label")) for item in _items(prediction.get("semanticGaps"))
    }
    prohibited = prediction.get("prohibitedVocabulary", [])
    return {
        "status": "scored",
        "releasedTermMapping": _f1(expected, actual),
        "semanticGapCoverage": _f1(expected_gaps, actual_gaps),
        "shaclConformance": 1.0 if prediction.get("shaclConforms") is True else 0.0,
        "prohibitedVocabularyCount": len(prohibited)
        if isinstance(prohibited, list)
        else 0,
    }


def score_scenario(gold: JsonObject, prediction: JsonObject | None) -> JsonObject:
    """Compare longitudinal checkpoints and explicit contradiction/provenance state."""

    if prediction is None:
        return {"status": "missing-output"}
    expected = {
        json.dumps(item, sort_keys=True) for item in _items(gold.get("checkpoints"))
    }
    actual = {
        json.dumps(item, sort_keys=True)
        for item in _items(prediction.get("checkpoints"))
    }
    return {
        "status": "scored",
        "checkpointAgreement": _f1(expected, actual),
        "temporalStateAgreement": float(prediction.get("temporalStateAgreement", 0.0)),
        "contradictionDetection": float(prediction.get("contradictionDetection", 0.0)),
        "provenanceAgreement": float(prediction.get("provenanceAgreement", 0.0)),
        "projectScopeAccuracy": float(prediction.get("projectScopeAccuracy", 0.0)),
    }


def score_retrieval(gold: JsonObject, prediction: JsonObject | None) -> JsonObject:
    """Score fact/citation sets and freshness/completeness/abstention decisions."""

    if prediction is None:
        return {"status": "missing-output"}
    expected = {
        str(item.get("questionId")): item
        for item in _items(gold.get("competencyAnswers"))
    }
    actual = {
        str(item.get("questionId")): item for item in _items(prediction.get("answers"))
    }
    rows: list[float] = []
    for question_id, answer in expected.items():
        candidate = actual.get(question_id)
        if candidate is None:
            rows.append(0.0)
            continue
        fact_score = _f1(
            set(map(str, answer.get("expectedFactIds", []))),
            set(map(str, candidate.get("factIds", []))),
        )["f1"]
        citation_score = _f1(
            set(map(str, answer.get("expectedCitationIds", []))),
            set(map(str, candidate.get("citationIds", []))),
        )["f1"]
        scalar = [
            fact_score,
            citation_score,
            1.0 if candidate.get("completeness") == answer.get("completeness") else 0.0,
            1.0 if candidate.get("freshness") == answer.get("freshness") else 0.0,
            1.0 if candidate.get("abstain") == answer.get("abstain") else 0.0,
        ]
        rows.append(statistics.fmean(scalar))
    return {
        "status": "scored",
        "questionCount": len(expected),
        "answerAgreement": statistics.fmean(rows) if rows else 0.0,
        "factualCorrectness": statistics.fmean(rows) if rows else 0.0,
        "citationCorrectness": statistics.fmean(rows) if rows else 0.0,
    }


def score_reviewer_utility(records: Sequence[Mapping[str, object]]) -> JsonObject:
    """Aggregate reviewer fields while rejecting raw text fields."""

    forbidden = {"rawText", "sourceText", "answerText", "comment"}
    if any(forbidden & set(record) for record in records):
        raise EvaluationError("reviewer utility contains prohibited raw sensitive data")
    if not records:
        return {"status": "not-available", "count": 0}
    numeric = {
        name: statistics.fmean(
            float(record[name])
            for record in records
            if isinstance(record.get(name), (int, float))
        )
        for name in ("reviewTimeSeconds", "usefulness", "trust")
        if any(isinstance(record.get(name), (int, float)) for record in records)
    }
    return {
        "status": "scored",
        "count": len(records),
        "dispositionCounts": dict(
            Counter(str(record.get("disposition", "missing")) for record in records)
        ),
        "correctionClassCounts": dict(
            Counter(str(record.get("correctionClass", "missing")) for record in records)
        ),
        **numeric,
    }


def score_operational(records: Sequence[Mapping[str, object]]) -> JsonObject:
    """Aggregate latency, usage, cost, failures, and accepted-candidate cost."""

    if not records:
        return {"status": "not-available", "count": 0}
    latencies = sorted(
        float(record["latencyMs"])
        for record in records
        if isinstance(record.get("latencyMs"), (int, float))
    )
    costs = [
        float(record["costUsd"])
        for record in records
        if isinstance(record.get("costUsd"), (int, float))
    ]
    failures = Counter(
        str(record.get("failureClass", "none"))
        for record in records
        if record.get("failureClass") not in (None, "none")
    )
    return {
        "status": "scored",
        "count": len(records),
        "latencyMs": {
            "p50": _percentile(latencies, 0.5),
            "p95": _percentile(latencies, 0.95),
        },
        "costUsd": sum(costs),
        "usage": {
            "inputTokens": sum(int(record.get("inputTokens", 0)) for record in records),
            "outputTokens": sum(
                int(record.get("outputTokens", 0)) for record in records
            ),
        },
        "failureCounts": dict(failures),
        "acceptedCandidateCostUsd": sum(
            float(record.get("costUsd", 0.0))
            for record in records
            if record.get("acceptedCandidate") is True
        ),
    }


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    index = min(len(values) - 1, max(0, math.ceil(fraction * len(values)) - 1))
    return values[index]


def classify_error(error: Mapping[str, object]) -> str:
    """Map an observed error to the finite Phase E taxonomy."""

    category = str(error.get("category", "runtime"))
    allowed = {
        "data",
        "annotation",
        "ontology",
        "prompt",
        "context",
        "tool",
        "model",
        "runtime",
    }
    if category not in allowed:
        raise EvaluationError(f"unknown baseline error category: {category}")
    return category


def build_evidence_report(
    loaded: LoadedDataset,
    *,
    config: Mapping[str, object],
    case_results: Mapping[str, JsonObject] | None = None,
    status: str = "SCORED",
) -> JsonObject:
    """Build a complete, digest-bound report with explicit case coverage."""

    results = case_results or {}
    coverage = [
        {
            "caseId": case.get("caseId"),
            "split": case.get("split"),
            "status": results.get(str(case.get("caseId")), {}).get(
                "status", "missing-output"
            ),
        }
        for case in loaded.cases
    ]
    missing = sum(row["status"] == "missing-output" for row in coverage)
    config_value = cast(JSONValue, dict(config))
    return {
        "reportVersion": "s12.evidence.v1",
        "evaluatorVersion": EVALUATOR_VERSION,
        "status": status,
        "datasetVersion": loaded.dataset.get("datasetVersion"),
        "manifestDigest": loaded.manifest.get("manifestDigest"),
        "configurationDigest": digest(config_value),
        "caseCoverage": coverage,
        "caseCount": len(coverage),
        "missingOutputCount": missing,
        "omittedCaseCount": 0,
        "hardInvariants": {"status": "not-evaluated" if missing else "evaluated"},
        "metrics": results,
        "rawSensitiveDataIncluded": False,
        "humanEvidence": loaded.dataset.get("humanEvidence") is True,
    }


def write_evidence_report(
    report: JsonObject, json_path: Path, markdown_path: Path
) -> None:
    """Write machine-readable and reviewable evidence without source text."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        f"# Sprint 12 Evidence Report `{report['reportVersion']}`",
        "",
        f"- Status: `{report['status']}`",
        f"- Dataset: `{report['datasetVersion']}`",
        f"- Manifest digest: `{report['manifestDigest']}`",
        f"- Configuration digest: `{report['configurationDigest']}`",
        f"- Cases: `{report['caseCount']}`; missing outputs: `{report['missingOutputCount']}`",
        f"- Human evidence: `{report['humanEvidence']}`",
        "",
        "The report contains identifiers and digests only; raw source text is excluded.",
        "",
    ]
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def missing_runtime_configuration(
    environment: Mapping[str, str] | None = None,
) -> list[str]:
    """Return required live baseline variables that are absent."""

    values = os.environ if environment is None else environment
    return [name for name in REQUIRED_RUNTIME_ENV if not values.get(name)]


def build_baseline_report(
    loaded: LoadedDataset, *, environment: Mapping[str, str] | None = None
) -> JsonObject:
    """Prepare a truthful baseline result; never substitute fixture replay for a run."""

    missing = missing_runtime_configuration(environment)
    status = (
        "NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION"
        if missing
        else "NOT_EXECUTED_ADAPTER_NOT_CONFIGURED"
    )
    config = {
        "release": "v0.6.0",
        "promptChange": False,
        "runtimeChange": False,
        "missingVariables": missing,
    }
    report = build_evidence_report(loaded, config=config, status=status)
    report["baseline"] = {
        "release": "v0.6.0",
        "execution": status,
        "missingRuntimeConfiguration": missing,
        "developmentAndValidationOnly": True,
    }
    report["errorTaxonomy"] = {
        "categories": [
            "data",
            "annotation",
            "ontology",
            "prompt",
            "context",
            "tool",
            "model",
            "runtime",
        ],
        "observations": [{"category": "runtime", "reason": status}],
    }
    return report


def main() -> None:
    """Generate a baseline report for the repository-visible Phase E fixture."""

    root = Path(__file__).resolve().parents[1]
    loaded = load_dataset(
        root / "evaluation/sprint-12/corpus/atomic-development-validation.v1.json",
        root / "evaluation/sprint-12/corpus/scenario-development-validation.v1.json",
        root
        / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v1.json",
    )
    report = build_baseline_report(loaded)
    write_evidence_report(
        report,
        root / "evaluation/sprint-12/baseline/baseline-report.v1.json",
        root / "evaluation/sprint-12/baseline/baseline-report.v1.md",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "caseCount": report["caseCount"],
                "missingOutputCount": report["missingOutputCount"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
