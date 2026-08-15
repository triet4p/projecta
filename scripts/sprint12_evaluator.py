#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai>=2,<3",
#     "pydantic>=2,<3",
# ]
# ///
"""Deterministic Sprint 12 Phase E evaluation harness.

The harness is deliberately independent from a model runtime. It validates the
versioned fixture, scores supplied model outputs, and fails closed when a live
baseline configuration is not available. Reports contain identifiers and
digests only; source text is never copied into evidence artifacts.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TypeAlias, cast

JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)
JsonObject: TypeAlias = dict[str, JSONValue]
JsonList: TypeAlias = list[JSONValue]
EVALUATOR_VERSION = "s12.evaluator.v1"
RUNTIME_REQUEST_TIMEOUT_SECONDS = 60
RUNTIME_RUN_BUDGET_SECONDS = 300
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
    span = _object(item.get("span", item.get("evidence", item)), "span")
    if "predicate" in item:
        label: object = (item.get("predicate"), item.get("targetEntityId"))
    else:
        label = item.get("type", item.get("targetEntityId"))
    return (
        span.get("start", span.get("startOffset")),
        span.get("end", span.get("endOffset")),
        label,
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
        if isinstance(prediction.get("abstention"), dict)
        else bool(prediction.get("abstentionReason"))
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


def _runtime_baseline(
    loaded: LoadedDataset,
    environment: Mapping[str, str],
    *,
    gateway_factory: Callable[[str, str], object] | None = None,
    schema_version: str = "m3.v1",
    operation_id: str = "s12-v0.6.0-baseline",
    profile_revision: str = "released-v0.6.0",
    prompt_variant: str = "m3.prompt.v2",
    collect_diagnostics: bool = False,
) -> tuple[dict[str, JsonObject], list[JsonObject], list[JsonObject], JsonObject]:
    """Run one bounded attempt per case through the released extraction gateway."""

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "apps" / "api" / "src"))
    from projecta_api.extraction.normalize import normalize_extraction
    from projecta_api.extraction.prompt import build_extraction_prompt
    from projecta_api.extraction.service import _response_schema
    from projecta_api.llm.gateway import GatewayRequest
    from projecta_api.llm.openai_responses import OpenAIResponsesGateway

    llm_type = environment["PROJECTA_LLM_TYPE"]
    if llm_type not in {"openai", "openai-response"}:
        raise EvaluationError(f"unsupported runtime LLM type: {llm_type}")
    gateway = (
        gateway_factory(
            environment["PROJECTA_LLM_BASE_URL"], environment["PROJECTA_LLM_API_KEY"]
        )
        if gateway_factory is not None
        else OpenAIResponsesGateway(
            base_url=environment["PROJECTA_LLM_BASE_URL"],
            api_key=environment["PROJECTA_LLM_API_KEY"],
        )
    )
    model = environment["PROJECTA_LLM_MODEL"]
    entity_types = [
        "Requirement",
        "Decision",
        "Question",
        "Task",
        "Risk",
        "Assumption",
        "Constraint",
        "ProgressClaim",
        "ResearchFinding",
    ]
    relation_predicates = [
        "implements",
        "blocks",
        "dependsOn",
        "supports",
        "answers",
        "resolves",
        "constrainedBy",
    ]
    case_results: dict[str, JsonObject] = {}
    operational: list[JsonObject] = []
    failures: list[JsonObject] = []
    diagnostics: list[JsonObject] = []

    async def evaluate_cases() -> None:
        for case in loaded.cases:
            case_id = _string(case.get("caseId"), "caseId")
            raw_text = _object(case.get("source"), f"{case_id}.source").get("rawText")
            if not isinstance(raw_text, str):
                raise EvaluationError(f"missing source text for {case_id}")
            started = monotonic()
            try:
                system, user = build_extraction_prompt(
                    raw_text,
                    entity_types,
                    relation_predicates,
                    [],
                    schema_version=schema_version,
                )
                if schema_version == "m3.v2":
                    user += (
                        "\nContract m3.v2: assign every emitted entity a unique local "
                        "candidateId. Relation sourceEntityId and targetEntityId may "
                        "reference those local candidate IDs or bounded same-project IDs. "
                        "For every evidence object, return exact text and its one-based "
                        "occurrence in the whole note; do not return offsets."
                    )
                if prompt_variant == "m3.prompt.v3.supersession-guard":
                    user += (
                        "\nSupersession guard: do not emit the released predicate "
                        "supersedes because it is not in the allowed predicate list. "
                        "Do not convert a clause whose meaning is only supersession "
                        "into a Requirement. If there is no standalone supported "
                        "entity, abstain. Preserve exact evidence quote and occurrence "
                        "and assign unique candidateId values to emitted entities."
                    )
                elif prompt_variant != "m3.prompt.v2":
                    raise EvaluationError(f"unsupported prompt variant: {prompt_variant}")
                response = await asyncio.wait_for(
                    gateway.extract(
                        GatewayRequest(
                            schemaVersion=schema_version,
                            modelId=model,
                            systemPrompt=system,
                            userPrompt=user,
                            responseSchema=_response_schema(
                                schema_version=schema_version
                            ),
                            sourceText=raw_text if schema_version == "m3.v2" else None,
                            timeoutSeconds=RUNTIME_REQUEST_TIMEOUT_SECONDS,
                            maxOutputTokens=4096,
                            requestId=f"s12-baseline-{case_id}",
                            operationId=operation_id,
                            profileRevision=profile_revision,
                        )
                    ),
                    timeout=RUNTIME_REQUEST_TIMEOUT_SECONDS,
                )
                normalized = normalize_extraction(raw_text, response.extraction, [])
                prediction = cast(
                    JsonObject, normalized.model_dump(mode="json", by_alias=True)
                )
                gold = _object(case.get("gold"), f"{case_id}.gold")
                case_results[case_id] = score_extraction(gold, prediction)
                usage = (
                    _object(prediction.get("usage"), "usage")
                    if isinstance(prediction.get("usage"), dict)
                    else {}
                )
                operational.append(
                    {
                        "caseId": case_id,
                        "split": case.get("split"),
                        "slice": _manifest_slice(loaded.manifest, case_id),
                        "latencyMs": int((monotonic() - started) * 1000),
                        "inputTokens": usage.get("inputTokens", 0) or 0,
                        "outputTokens": usage.get("outputTokens", 0) or 0,
                        "costUsd": 0.0,
                        "failureClass": "none",
                    }
                )
            except Exception as error:  # noqa: BLE001 - sanitized baseline evidence
                category = _runtime_error_category(error)
                failure = {
                    "caseId": case_id,
                    "category": category,
                    "failureClass": str(
                        getattr(error, "error_class", type(error).__name__)
                    ),
                }
                failures.append(failure)
                if collect_diagnostics:
                    diagnostic = getattr(error, "diagnostic", {})
                    diagnostics.append(
                        {
                            "caseId": case_id,
                            "failureClass": failure["failureClass"],
                            "category": category,
                            "diagnostic": diagnostic if isinstance(diagnostic, dict) else {},
                        }
                    )
                case_results[case_id] = {
                    "status": "missing-output",
                    "failureClass": failure["failureClass"],
                    "category": category,
                }
                operational.append(
                    {
                        "caseId": case_id,
                        "split": case.get("split"),
                        "slice": _manifest_slice(loaded.manifest, case_id),
                        "latencyMs": int((monotonic() - started) * 1000),
                        "inputTokens": 0,
                        "outputTokens": 0,
                        "costUsd": 0.0,
                        "failureClass": failure["failureClass"],
                    }
                )

    async def run_with_budget() -> None:
        try:
            async with asyncio.timeout(RUNTIME_RUN_BUDGET_SECONDS):
                await evaluate_cases()
        except TimeoutError:
            for case in loaded.cases:
                case_id = _string(case.get("caseId"), "caseId")
                if case_id in case_results:
                    continue
                failure = {
                    "caseId": case_id,
                    "category": "runtime",
                    "failureClass": "baseline_run_budget_exceeded",
                }
                failures.append(failure)
                case_results[case_id] = {
                    "status": "missing-output",
                    "failureClass": failure["failureClass"],
                    "category": failure["category"],
                }
                operational.append(
                    {
                        "caseId": case_id,
                        "split": case.get("split"),
                        "slice": _manifest_slice(loaded.manifest, case_id),
                        "latencyMs": RUNTIME_RUN_BUDGET_SECONDS * 1000,
                        "inputTokens": 0,
                        "outputTokens": 0,
                        "costUsd": 0.0,
                        "failureClass": failure["failureClass"],
                    }
                )

    asyncio.run(run_with_budget())
    config = {
        "release": "v0.6.0",
        "schemaVersion": schema_version,
        "llmType": llm_type,
        "model": model,
        "baseUrl": environment["PROJECTA_LLM_BASE_URL"],
        "promptVersion": prompt_variant,
        "evaluatorVersion": EVALUATOR_VERSION,
        "manifestDigest": loaded.manifest.get("manifestDigest"),
        "apiKeyPresent": True,
        "oneAttemptPerCase": True,
        "retryPolicy": "none",
        "requestTimeoutSeconds": RUNTIME_REQUEST_TIMEOUT_SECONDS,
        "runBudgetSeconds": RUNTIME_RUN_BUDGET_SECONDS,
        "samplingConfiguration": {
            "temperature": "provider-default",
            "topP": "provider-default",
            "seed": "provider-controlled",
        },
    }
    if collect_diagnostics:
        return case_results, operational, failures, config, diagnostics  # type: ignore[return-value]
    return case_results, operational, failures, config


def _manifest_slice(manifest: JsonObject, case_id: str) -> str | None:
    for entry in _list(manifest.get("atomicCases"), "manifest.atomicCases"):
        if entry.get("caseId") == case_id:
            value = entry.get("slice")
            return value if isinstance(value, str) else None
    return None


def _runtime_error_category(error: Exception) -> str:
    error_class = str(getattr(error, "error_class", "runtime"))
    if error_class in {"schema_invalid", "normalization_invalid", "invalid_evidence"}:
        return "model"
    if error_class in {"policy_rejection", "hallucinated_link", "cross_project_link"}:
        return "context"
    return "runtime"


def build_baseline_report(
    loaded: LoadedDataset, *, environment: Mapping[str, str] | None = None
) -> JsonObject:
    """Prepare a truthful baseline result; never substitute fixture replay for a run."""

    missing = missing_runtime_configuration(environment)
    if not missing:
        case_results, operational, failures, config = _runtime_baseline(
            loaded, os.environ if environment is None else environment
        )
        status = (
            "RUNTIME_BACKED_SCORED" if not failures else "RUNTIME_BACKED_WITH_FAILURES"
        )
        report = build_evidence_report(
            loaded, config=config, case_results=case_results, status=status
        )
        report["operational"] = score_operational(operational)
        report["operationalRecords"] = operational
        report["failureCount"] = len(failures)
        report["hardInvariants"] = {
            "status": "PASS" if not failures else "FAIL",
            "schemaValidity": not failures,
            "splitIntegrity": True,
            "datasetDigestBinding": True,
            "heldOutNonLeakage": True,
        }
        report["baseline"] = {
            "release": "v0.6.0",
            "execution": status,
            "developmentAndValidationOnly": True,
            "oneAttemptPerCase": True,
            "retryPolicy": "none",
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
            "observations": failures,
        }
        return report
    status = "NOT_EXECUTED_MISSING_RUNTIME_CONFIGURATION"
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
    report_path = root / "evaluation/sprint-12/baseline/baseline-report.v1.json"
    lock_path = root / "evaluation/sprint-12/baseline/baseline-lock.v1.json"
    if lock_path.exists() and report_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        report_digest = "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest()
        if lock.get("reportDigest") == report_digest:
            raise SystemExit(
                "historical Sprint 12 v0.6.0 baseline is locked; write a new versioned report"
            )
    loaded = load_dataset(
        root / "evaluation/sprint-12/corpus/atomic-development-validation.v1.json",
        root / "evaluation/sprint-12/corpus/scenario-development-validation.v1.json",
        root
        / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v1.json",
    )
    report = build_baseline_report(loaded)
    write_evidence_report(
        report,
        report_path,
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
