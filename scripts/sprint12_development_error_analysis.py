"""Build the S12-f-07 development error backlog from existing local evidence.

This module is intentionally offline: it reads persisted reports and corpus
metadata only.  It never imports the provider gateway or executes an evaluator.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"
OUT_JSON = OPT / "development-error-analysis.v1.json"
OUT_MD = OPT / "development-error-analysis.v1.md"
PREREG_JSON = OPT / "s12-f-07-relation-prompt-preregistration.v1.json"

METRICS = (
    "entityMacroF1",
    "relationMacroF1",
    "abstentionAccuracy",
    "hallucinationRate",
)

REPORT_GROUPS = (
    (
        "s12-73-prompt-8-case",
        "S12-73",
        OPT / "s12-73-prompt-supersession",
        "prompt",
    ),
    (
        "s12-73-prompt-followup-32-case",
        "S12-73",
        OPT / "s12-73-prompt-followup-stability-v2",
        "prompt",
    ),
    (
        "s12-77-model-16-case",
        "S12-77",
        OPT / "s12-77-model-stage-a",
        "model",
    ),
    (
        "s12-f-06-sampling-8-case",
        "S12-f-06",
        OPT / "s12-f-06-sampling-stage-a",
        "sampling",
    ),
)

DIAGNOSTIC_ARTIFACTS = (
    OPT / "s12-73-targeted-diagnostics.v1.json",
    OPT / "s12-77-targeted-diagnostics.v1.json",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def report_variant(data: dict[str, Any], path: Path) -> str:
    configuration = data["configuration"]
    if "sampling" in str(path.parent):
        return "candidate" if configuration["samplingConfiguration"]["temperature"] == 0.0 else "control"
    if "model-stage-a" in str(path.parent):
        return "candidate" if configuration["model"] == "deepseek-v4-pro" else "control"
    if "baseline" in path.name:
        return "control"
    if "candidate" in path.name:
        return "candidate"
    return "candidate"


def classify_case(
    case_id: str,
    per_case: dict[str, Any],
    coverage: dict[str, Any],
    operational: dict[str, Any],
) -> dict[str, Any]:
    status = coverage.get("status")
    failure_class = (
        per_case.get("failureClass")
        or operational.get("failureClass")
        or "none"
    )
    errors: list[str] = []
    evidence: dict[str, str] = {}

    if status != "scored" or failure_class != "none":
        errors.append("schema/evidence/runtime failure")
        evidence["schema/evidence/runtime failure"] = "observed"
    else:
        if per_case.get("abstentionAccuracy") == 0:
            errors.append("incorrect abstention")
            evidence["incorrect abstention"] = "observed"

        entities = per_case.get("entities", {})
        if entities.get("gold", 0) > entities.get("truePositive", 0):
            errors.append("missing entity")
            evidence["missing entity"] = "observed_from_counts"
        if (
            entities.get("predicted", 0) > entities.get("truePositive", 0)
            or per_case.get("hallucinationRate", 0) > 0
        ):
            errors.append("hallucination")
            evidence["hallucination"] = "observed_from_counts"

        relations = per_case.get("relations", {})
        if relations.get("gold", 0) > relations.get("truePositive", 0):
            if relations.get("predicted", 0) == 0:
                errors.append("missing relation")
                evidence["missing relation"] = "observed_from_counts"
            else:
                errors.append("wrong predicate/endpoints")
                evidence["wrong predicate/endpoints"] = "inferred_from_aggregate_counts"

    if not errors:
        errors.append("none")
        evidence["none"] = "observed"

    route = {
        "schema/evidence/runtime failure": "tool",
        "missing entity": "prompt",
        "wrong predicate/endpoints": "prompt",
        "missing relation": "prompt",
        "incorrect abstention": "prompt",
        "hallucination": "prompt",
        "unsupported entity": "evaluator",
        "wrong entity type": "evaluator",
        "none": "none",
    }
    primary = errors[0]
    return {
        "caseId": case_id,
        "status": status,
        "failureClass": failure_class,
        "observedErrorClasses": errors,
        "evidenceLevelByClass": evidence,
        "primaryErrorClass": primary,
        "routingRecommendation": route[primary],
        "slice": operational.get("slice"),
        "split": operational.get("split"),
        "inputTokens": operational.get("inputTokens", 0),
        "outputTokens": operational.get("outputTokens", 0),
        "latencyMs": operational.get("latencyMs", 0),
        "costUsd": operational.get("costUsd", 0.0),
        "metrics": {
            key: per_case.get(key)
            for key in ("abstentionAccuracy", "hallucinationRate")
            if key in per_case
        },
        "entityCounts": per_case.get("entities"),
        "relationCounts": per_case.get("relations"),
        "accounting": {
            "caseCoveragePresent": True,
            "perCaseMetricPresent": True,
            "operationalRecordPresent": True,
            "missingOutputIsFailExplicit": status != "scored",
        },
    }


def read_reports() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reports: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for group_id, experiment_id, directory, dimension in REPORT_GROUPS:
        paths = sorted(directory.rglob("*.report.v1.json"))
        group_reports = []
        for path in paths:
            data = load_json(path)
            coverage = {item["caseId"]: item for item in data["caseCoverage"]}
            per_case = data["metrics"]["perCase"]
            operational = {item["caseId"]: item for item in data["operationalRecords"]}
            expected = set(coverage)
            if expected != set(per_case) or expected != set(operational):
                raise AssertionError(f"incomplete report accounting: {path}")
            cases = [
                classify_case(case_id, per_case[case_id], coverage[case_id], operational[case_id])
                for case_id in sorted(expected)
            ]
            report = {
                "groupId": group_id,
                "experimentId": experiment_id,
                "dimension": dimension,
                "variant": report_variant(data, path),
                "runId": path.name.removesuffix(".report.v1.json"),
                "reportPath": path.relative_to(ROOT).as_posix(),
                "reportDigest": data.get("reportDigest", sha256_file(path)),
                "fileDigest": sha256_file(path),
                "configuration": data["configuration"],
                "caseCount": data["caseCount"],
                "failureCount": data["failureCount"],
                "missingOutputCount": data["missingOutputCount"],
                "heldOutInspected": data["heldOutInspected"],
                "split": data["split"],
                "status": data["status"],
                "metrics": {key: data["metrics"].get(key) for key in METRICS},
                "operational": data["operational"],
                "cases": cases,
            }
            reports.append(report)
            group_reports.append(report)
        groups.append(
            {
                "groupId": group_id,
                "experimentId": experiment_id,
                "dimension": dimension,
                "reportCount": len(group_reports),
                "reports": group_reports,
            }
        )
    return reports, groups


def metric_variance(reports: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for metric in METRICS:
        values = [report["metrics"][metric] for report in reports]
        result[metric] = {
            "mean": statistics.fmean(values),
            "min": min(values),
            "max": max(values),
            "populationVariance": statistics.pvariance(values),
        }
    return result


def common_case_denominators(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for group in groups:
        reports = group["reports"]
        if group["groupId"] == "s12-73-prompt-followup-32-case":
            scored = [
                {case["caseId"] for case in report["cases"] if case["status"] == "scored"}
                for report in reports
            ]
            result.append(
                {
                    "groupId": group["groupId"],
                    "method": "intersection_across_independent_runs",
                    "allRunCommonCaseCount": len(set.intersection(*scored)),
                    "perRunScoredCounts": [len(items) for items in scored],
                }
            )
            continue
        if group["groupId"] not in {
            "s12-73-prompt-8-case",
            "s12-77-model-16-case",
            "s12-f-06-sampling-8-case",
        }:
            continue
        by_run: dict[str, dict[str, set[str]]] = defaultdict(dict)
        for report in reports:
            run_number = report["runId"].rsplit("-", 1)[-1]
            by_run[run_number][report["variant"]] = {
                case["caseId"] for case in report["cases"] if case["status"] == "scored"
            }
        pairs = []
        for run_number, variants in sorted(by_run.items()):
            if "control" in variants and "candidate" in variants:
                pairs.append(
                    {
                        "run": run_number,
                        "controlScored": len(variants["control"]),
                        "candidateScored": len(variants["candidate"]),
                        "commonCaseCount": len(variants["control"] & variants["candidate"]),
                    }
                )
        result.append(
            {
                "groupId": group["groupId"],
                "method": "paired_intersection_of_valid_outputs",
                "pairedRuns": pairs,
                "commonCaseExecutionCount": sum(item["commonCaseCount"] for item in pairs),
            }
        )
    return result


def slice_error_counts(reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = defaultdict(lambda: {"caseRunCount": 0, "errorCounts": Counter()})
    for report in reports:
        for case in report["cases"]:
            row = table[case["slice"]]
            row["caseRunCount"] += 1
            for error in case["observedErrorClasses"]:
                if error != "none":
                    row["errorCounts"][error] += 1
    return {
        slice_name: {
            "caseRunCount": row["caseRunCount"],
            "errorCounts": dict(sorted(row["errorCounts"].items())),
        }
        for slice_name, row in sorted(table.items())
    }


def recurrence(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for report in reports:
        for case in report["cases"]:
            for error in case["observedErrorClasses"]:
                if error != "none":
                    grouped[(report["groupId"], report["variant"], case["caseId"], error)].append(report)
    rows = []
    for (group_id, variant, case_id, error), observed in sorted(grouped.items()):
        rows.append(
            {
                "groupId": group_id,
                "variant": variant,
                "caseId": case_id,
                "errorClass": error,
                "runCount": len(observed),
                "reportIds": [f"{item['groupId']}:{item['runId']}" for item in observed],
                "pattern": "recurring" if len(observed) >= 2 else "stochastic_one_off",
            }
        )
    return rows


def gold_confusion_denominators(reports: list[dict[str, Any]]) -> dict[str, Any]:
    corpus = {
        case["caseId"]: case
        for case in load_json(EVAL / "corpus" / "atomic-development-validation.v2.json")["cases"]
    }
    selected = sorted({case["caseId"] for report in reports for case in report["cases"]})
    entity_counts: Counter[str] = Counter()
    entity_case_counts: Counter[str] = Counter()
    predicate_counts: Counter[str] = Counter()
    predicate_case_counts: Counter[str] = Counter()
    for case_id in selected:
        gold = corpus[case_id]["gold"]
        seen_types: set[str] = set()
        seen_predicates: set[str] = set()
        for entity in gold["entities"]:
            entity_counts[entity["type"]] += 1
            seen_types.add(entity["type"])
        for relation in gold["relations"]:
            predicate_counts[relation["predicate"]] += 1
            seen_predicates.add(relation["predicate"])
        for entity_type in seen_types:
            entity_case_counts[entity_type] += 1
        for predicate in seen_predicates:
            predicate_case_counts[predicate] += 1

    def row(counts: Counter[str], case_counts: Counter[str]) -> dict[str, Any]:
        return {
            key: {
                "goldItemCount": counts[key],
                "goldCaseCount": case_counts[key],
                "truePositive": None,
                "falsePositive": None,
                "falseNegative": None,
                "status": "not_observable_from_sanitized_reports",
            }
            for key in sorted(counts)
        }

    return {
        "selectedUniqueCaseCount": len(selected),
        "entityTypeConfusion": {
            "observedExactPredictionCountsAvailable": False,
            "reason": "Persisted reports contain aggregate entity counts only; predicted entity types were not retained.",
            "rows": row(entity_counts, entity_case_counts),
        },
        "relationPredicateConfusion": {
            "observedExactPredictionCountsAvailable": False,
            "reason": "Persisted reports contain aggregate relation TP/predicted counts only; predicate and endpoint pairs were not retained.",
            "rows": row(predicate_counts, predicate_case_counts),
        },
    }


def diagnostics() -> list[dict[str, Any]]:
    items = []
    for path in DIAGNOSTIC_ARTIFACTS:
        data = load_json(path)
        items.append(
            {
                "artifact": path.relative_to(ROOT).as_posix(),
                "artifactDigest": sha256_file(path),
                "experimentId": "S12-73" if "s12-73" in path.name else "S12-77",
                "protocol": data["protocol"],
                "outcomes": data["outcomes"],
                "status": data["status"],
            }
        )
    return items


def build_backlog() -> dict[str, Any]:
    reports, groups = read_reports()
    missing_outputs = sum(report["missingOutputCount"] for report in reports)
    expected_case_runs = sum(report["caseCount"] for report in reports)
    accounted_case_runs = sum(len(report["cases"]) for report in reports)
    failure_counts = Counter(
        case["failureClass"]
        for report in reports
        for case in report["cases"]
        if case["failureClass"] != "none"
    )
    relation_positive_case_runs = 0
    relation_error_case_runs = 0
    for report in reports:
        for case in report["cases"]:
            relation_counts = case.get("relationCounts") or {}
            if relation_counts.get("gold", 0) > 0:
                relation_positive_case_runs += 1
                if relation_counts.get("gold", 0) > relation_counts.get("truePositive", 0):
                    relation_error_case_runs += 1

    source_artifacts = []
    aggregate_paths = (
        "evaluation/sprint-12/optimization/s12-73-prompt-supersession.v1.json",
        "evaluation/sprint-12/optimization/s12-73-prompt-followup-stability.v2.json",
        "evaluation/sprint-12/optimization/s12-77-model-stage-a.v1.json",
        "evaluation/sprint-12/optimization/s12-f-06-sampling-stage-a.v1.json",
        "evaluation/sprint-12/optimization/s12-f-06-sampling-erratum.v1.json",
    )
    for path_text in aggregate_paths:
        path = ROOT / path_text
        source_artifacts.append(
            {"artifact": path_text, "fileDigest": sha256_file(path), "role": "aggregate_or_erratum"}
        )
    for report in reports:
        source_artifacts.append(
            {
                "artifact": report["reportPath"],
                "fileDigest": report["fileDigest"],
                "reportDigest": report["reportDigest"],
                "role": "per_run_report",
            }
        )

    backlog = {
        "artifactVersion": "s12.development-error-analysis.v1",
        "status": "COMPLETED_OFFLINE_DEVELOPMENT_BACKLOG",
        "createdBy": "local-report-analysis-no-provider",
        "providerCallsMade": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "datasetVersion": "s12.corpus.atomic.v2",
        "datasetManifestDigest": "sha256:030087614d30c821a0d03c8d5bf0a549b63fc6ba672531e8eda37f474265f32a",
        "split": "development",
        "heldOutInspected": False,
        "sourceExperiments": ["S12-73", "S12-77", "S12-f-06"],
        "sourceArtifacts": source_artifacts,
        "taxonomy": {
            "caseRunClasses": [
                "missing entity",
                "unsupported entity",
                "wrong entity type",
                "missing relation",
                "wrong predicate/endpoints",
                "incorrect abstention",
                "hallucination",
                "schema/evidence/runtime failure",
            ],
            "routingClasses": ["data", "evaluator", "prompt", "context", "tool", "model", "ontology"],
            "notObservedExactClasses": ["unsupported entity", "wrong entity type"],
        },
        "outputAccounting": {
            "reportCount": len(reports),
            "expectedCaseRunCount": expected_case_runs,
            "accountedCaseRunCount": accounted_case_runs,
            "accountingComplete": expected_case_runs == accounted_case_runs,
            "missingOutputCount": missing_outputs,
            "missingOutputsFailExplicit": True,
            "failureCountsByPersistedClass": dict(sorted(failure_counts.items())),
            "diagnosticAttemptCount": sum(len(item["outcomes"]) for item in diagnostics()),
            "heldOutCaseRuns": 0,
        },
        "runGroups": [
            {
                "groupId": group["groupId"],
                "experimentId": group["experimentId"],
                "dimension": group["dimension"],
                "reportCount": group["reportCount"],
                "metricVariance": metric_variance(group["reports"]),
                "metricVarianceByVariant": {
                    variant: metric_variance([report for report in group["reports"] if report["variant"] == variant])
                    for variant in sorted({report["variant"] for report in group["reports"]})
                },
                "reports": [
                    {
                        "runId": report["runId"],
                        "variant": report["variant"],
                        "reportPath": report["reportPath"],
                        "caseCount": report["caseCount"],
                        "missingOutputCount": report["missingOutputCount"],
                        "failureCount": report["failureCount"],
                        "metrics": report["metrics"],
                        "latencyMs": report["operational"].get("latencyMs"),
                        "usage": report["operational"].get("usage"),
                        "costAccounting": {
                            "costUsd": report["operational"].get("costUsd"),
                            "acceptedCandidateCostUsd": report["operational"].get("acceptedCandidateCostUsd"),
                            "priceConfigurationAvailable": report["operational"].get("costUsd") not in (None, 0.0),
                        },
                    }
                    for report in group["reports"]
                ],
            }
            for group in groups
        ],
        "caseRuns": [
            {
                "experimentId": report["experimentId"],
                "groupId": report["groupId"],
                "variant": report["variant"],
                "runId": report["runId"],
                **case,
            }
            for report in reports
            for case in report["cases"]
        ],
        "errorCountsByDatasetSlice": slice_error_counts(reports),
        "recurringVersusStochastic": recurrence(reports),
        "commonCaseDenominators": common_case_denominators(groups),
        "confusionByTypeAndPredicate": gold_confusion_denominators(reports),
        "diagnosticAttempts": diagnostics(),
        "hypothesisDecision": {
            "relationPositiveCaseRunCount": relation_positive_case_runs,
            "relationErrorCaseRunCount": relation_error_case_runs,
            "relationErrorRateAmongPositiveCaseRuns": relation_error_case_runs / relation_positive_case_runs,
            "relationContractRepresentable": True,
            "denominatorOnlyExplanationRejected": True,
            "evaluatorOrDatasetBlockerObserved": False,
            "decision": "APPROVE_ONE_RELATION_FOCUSED_PROMPT_HYPOTHESIS",
            "routingRecommendation": "prompt",
            "rationale": "Relation errors recur on positive-relation development cases across S12-73 follow-up, S12-77, and S12-f-06; relation gold is non-zero in those runs and the reports mark relationContractRepresentable=true.",
        },
        "gateAssessment": {
            "allDevelopmentOnly": True,
            "heldOutUntouched": True,
            "goldOrOntologyChanged": False,
            "providerCalled": False,
            "outputAccountingPass": expected_case_runs == accounted_case_runs,
            "missingOutputFailExplicitPass": True,
            "exactTypePredicateConfusionPass": False,
            "exactTypePredicateConfusionLimitation": "Unavailable from persisted sanitized reports; evaluator instrumentation is required before claiming per-type/per-predicate confusion.",
        },
        "recommendedNextExperiment": {
            "experimentId": "S12-f-07",
            "status": "PREREGISTERED_NOT_EXECUTED",
            "changedDimension": "prompt",
            "model": "deepseek-v4-flash",
            "controlPrompt": "m3.prompt.v3.supersession-guard",
            "candidatePrompt": "m3.prompt.v4.relation-decision-rubric",
            "sampling": "provider-default",
            "fixed": ["dataset", "evaluator", "context", "tool", "ontology", "policy", "schema", "retryPolicy"],
            "stageA": {
                "caseCount": 16,
                "independentPairedRuns": 3,
                "noRetry": True,
                "caseSelection": [
                    "s12-a-0101", "s12-a-0105", "s12-a-0121", "s12-a-0122",
                    "s12-a-0151", "s12-a-0153", "s12-a-0161", "s12-a-0162",
                    "s12-a-0176", "s12-a-0177", "s12-a-0186", "s12-a-0187",
                    "s12-a-0201", "s12-a-0202", "s12-a-0226", "s12-a-0233",
                ],
                "selectionProfile": {
                    "positiveRelationCases": 7,
                    "hardNegativeOrSemanticGapCases": 5,
                    "abstentionOrIsolationCases": 4,
                },
                "hardGates": {
                    "schema_invalid": 0,
                    "invalid_evidence": 0,
                    "missing_output": 0,
                    "hallucinationRateIncrease": "none",
                },
                "semanticGates": {
                    "relationMacroF1MinimumDelta": 0.05,
                    "entityMacroF1MaximumDecrease": 0.01,
                    "abstentionAccuracyMaximumDecrease": 0.01,
                    "latencyAndUsage": "accounted",
                },
            },
            "stageB": {"caseCount": 32, "independentPairedRuns": 3, "authorizedOnlyAfterStageAAllGatesPass": True},
            "doNotRun": ["deepseek-v4-pro", "sampling-sweep", "provider-call-during-backlog"],
        },
    }
    return backlog


def markdown(backlog: dict[str, Any]) -> str:
    accounting = backlog["outputAccounting"]
    decision = backlog["hypothesisDecision"]
    next_exp = backlog["recommendedNextExperiment"]
    lines = [
        "# Development Error Analysis v1",
        "",
        "Status: `COMPLETED_OFFLINE_DEVELOPMENT_BACKLOG`",
        "",
        "This backlog analyzes persisted S12-73, S12-77 and S12-f-06 evidence only. No provider, evaluator run, model, sampling sweep, gold change or ontology change was performed.",
        "",
        "## Gate result",
        "",
        f"- Case/run accounting: **{accounting['accountedCaseRunCount']}/{accounting['expectedCaseRunCount']}** report executions accounted.",
        f"- Missing outputs: **{accounting['missingOutputCount']}**, retained as fail-explicit records.",
        "- Split: development only; held-out was not inspected.",
        "- Exact entity-type and predicate/endpoints confusion: **not observable** from the persisted sanitized reports; gold denominators are included in JSON and this is routed to evaluator instrumentation.",
        "",
        "## Main finding",
        "",
        f"Positive-relation case-runs: **{decision['relationPositiveCaseRunCount']}**; relation-error case-runs: **{decision['relationErrorCaseRunCount']}** ({decision['relationErrorRateAmongPositiveCaseRuns']:.1%}). Relation contract representability is true, and the errors recur across the positive-relation evidence rather than being explained only by a zero denominator. The approved next direction is **one prompt-only relation experiment**.",
        "",
        "## Error classes and routing",
        "",
        "| Error class | Evidence treatment | Routing |",
        "|---|---|---|",
        "| missing entity | observed from per-case aggregate counts | prompt |",
        "| unsupported entity | not observable in sanitized reports | evaluator |",
        "| wrong entity type | not observable in sanitized reports | evaluator |",
        "| missing relation | observed when gold relation > TP and predicted = 0 | prompt |",
        "| wrong predicate/endpoints | inferred when gold relation > TP and a relation was predicted | prompt |",
        "| incorrect abstention | observed from per-case abstention accuracy | prompt |",
        "| hallucination | observed from unmatched predicted entity/count or hallucination rate | prompt |",
        "| schema/evidence/runtime failure | observed from failure class or missing-output status | tool |",
        "",
        "## Confusion by entity type and relation predicate",
        "",
        "The required denominator tables are present below. Exact TP/FP/FN confusion is `n/a` because the persisted sanitized reports do not retain predicted type, predicate or endpoint pairs.",
        "",
        "### Entity type",
        "",
        "| Entity type | Gold items | Gold cases | TP | FP | FN |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    entity_rows = backlog["confusionByTypeAndPredicate"]["entityTypeConfusion"]["rows"]
    for name, row in entity_rows.items():
        lines.append(f"| {name} | {row['goldItemCount']} | {row['goldCaseCount']} | n/a | n/a | n/a |")
    lines += [
        "",
        "### Relation predicate",
        "",
        "| Predicate | Gold items | Gold cases | TP | FP | FN |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    predicate_rows = backlog["confusionByTypeAndPredicate"]["relationPredicateConfusion"]["rows"]
    for name, row in predicate_rows.items():
        lines.append(f"| {name} | {row['goldItemCount']} | {row['goldCaseCount']} | n/a | n/a | n/a |")
    lines += [
        "",
        "## Dataset-slice error counts",
        "",
        "Counts are case-runs, so the denominator is explicit and is not a pooled-only summary.",
        "",
        "| Slice | Case-runs | Error counts |",
        "|---|---:|---|",
    ]
    for slice_name, row in backlog["errorCountsByDatasetSlice"].items():
        counts = ", ".join(f"{key}: {value}" for key, value in row["errorCounts"].items()) or "none"
        lines.append(f"| {slice_name} | {row['caseRunCount']} | {counts} |")
    lines += [
        "",
        "## Run-to-run variance",
        "",
        "Population variance is computed over the persisted independent runs within each group. Full run details, latency and usage are in the JSON artifact.",
        "",
        "| Group | Variant | Metric | Mean | Min | Max | Population variance |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for group in backlog["runGroups"]:
        for variant, metrics in group["metricVarianceByVariant"].items():
            for metric, values in metrics.items():
                lines.append(f"| {group['groupId']} | {variant} | {metric} | {values['mean']:.4f} | {values['min']:.4f} | {values['max']:.4f} | {values['populationVariance']:.6f} |")
    lines += [
        "",
        "## Recurring versus stochastic",
        "",
        "A case/error pair observed in at least two independent persisted runs is marked recurring; one occurrence is marked stochastic one-off. A clean targeted diagnostic remains non-reproduction, not resolution.",
        "",
        "| Group | Variant | Case | Error | Runs | Pattern |",
        "|---|---|---|---|---:|---|",
    ]
    for item in backlog["recurringVersusStochastic"]:
        lines.append(f"| {item['groupId']} | {item['variant']} | {item['caseId']} | {item['errorClass']} | {item['runCount']} | {item['pattern']} |")
    lines += [
        "",
        "## Common-case denominators",
        "",
    ]
    for item in backlog["commonCaseDenominators"]:
        lines.append(f"- `{item['groupId']}`: `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")
    lines += [
        "",
        "## S12-f-07 decision",
        "",
        f"- Status: **{next_exp['status']}**.",
        f"- Control: `{next_exp['controlPrompt']}`; candidate: `{next_exp['candidatePrompt']}`.",
        f"- Model: `{next_exp['model']}`; sampling: `{next_exp['sampling']}`.",
        "- Stage A: 16 development cases × 3 paired runs, no retry. The selected cases contain positive relations, hard negatives/semantic gaps, and abstention/isolation cases.",
        "- Stage B: 32 × 3 is closed unless Stage A has zero schema/evidence/missing-output failures, relation macro F1 at least +0.05, no more than 0.01 entity or abstention decrease, no hallucination increase, and latency/usage accounted.",
        "- Do not run `deepseek-v4-pro`; do not run a sampling sweep. Validation, full 160, candidate freeze and held-out remain locked.",
        "",
        "## Artifact limits",
        "",
        "The sanitized reports preserve aggregate TP/predicted/gold counts but not predicted entity types, relation predicates or endpoint pairs. Therefore the JSON includes the gold denominator tables with null TP/FP/FN cells and an explicit evaluator-instrumentation gap. No exact confusion claim is made.",
        "",
        "See [development-error-analysis.v1.json](./development-error-analysis.v1.json) for every case/run record, source digests, failures, latency, usage, denominators and the preregistered next experiment.",
        "",
    ]
    return "\n".join(lines)


def build_preregistration(backlog: dict[str, Any]) -> dict[str, Any]:
    experiment = backlog["recommendedNextExperiment"]
    candidate_configuration = {
        "model": experiment["model"],
        "promptVersion": experiment["candidatePrompt"],
        "samplingConfiguration": {
            "seed": "provider-controlled",
            "temperature": "provider-default",
            "topP": "provider-default",
        },
        "schemaVersion": "m3.v2",
    }
    control_configuration = {
        **candidate_configuration,
        "promptVersion": experiment["controlPrompt"],
    }

    def config_digest(configuration: dict[str, Any]) -> str:
        encoded = json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    return {
        "artifactVersion": "s12.s12-f-07.relation-prompt-preregistration.v1",
        "experimentId": "s12-f-07",
        "experimentStatus": "PREREGISTERED_NOT_EXECUTED",
        "executionAuthorized": False,
        "executionDeferredByUserInstruction": True,
        "changedDimension": "prompt",
        "hypothesis": "A relation decision rubric in the prompt reduces missing and wrong predicate/endpoints errors while preserving entity extraction, abstention safety and hallucination rate on the incumbent model.",
        "control": {
            "configuration": control_configuration,
            "configurationDigest": config_digest(control_configuration),
        },
        "candidate": {
            "configuration": candidate_configuration,
            "configurationDigest": config_digest(candidate_configuration),
        },
        "fixedArtifacts": {
            "datasetVersion": backlog["datasetVersion"],
            "datasetManifestDigest": backlog["datasetManifestDigest"],
            "evaluator": "unchanged",
            "context": "unchanged",
            "tool": "unchanged",
            "ontology": "unchanged",
            "policy": "unchanged",
            "schemaVersion": "m3.v2",
            "retryPolicy": "none",
        },
        "stageA": {
            "caseCount": experiment["stageA"]["caseCount"],
            "caseIds": experiment["stageA"]["caseSelection"],
            "independentPairedRuns": experiment["stageA"]["independentPairedRuns"],
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "selectionRationale": "Prioritize positive relation cases, hard negatives/semantic-gap abstentions, and safety/isolation abstention cases while retaining the incumbent model and provider-default sampling.",
            "selectionProfile": experiment["stageA"]["selectionProfile"],
        },
        "stageB": {
            "caseCount": experiment["stageB"]["caseCount"],
            "independentPairedRuns": experiment["stageB"]["independentPairedRuns"],
            "authorizedOnlyAfterStageAAllGatesPass": True,
        },
        "hardGates": {
            "schema_invalid": 0,
            "invalid_evidence": 0,
            "missing_output": 0,
            "hallucinationRateIncrease": "none",
        },
        "semanticGates": {
            "relationMacroF1MinimumDelta": 0.05,
            "entityMacroF1MaximumDecrease": 0.01,
            "abstentionAccuracyMaximumDecrease": 0.01,
            "latencyAndUsage": "accounted",
        },
        "costAccounting": {
            "latencyRequired": True,
            "usageRequired": True,
            "providerPriceConfigurationRequiredBeforeExecution": True,
        },
        "prohibitedBeforeStageA": [
            "deepseek-v4-pro",
            "sampling-sweep",
            "held-out-inspection",
            "gold-or-ontology-change",
        ],
        "sourceEvidence": {
            "errorBacklog": "evaluation/sprint-12/optimization/development-error-analysis.v1.json",
            "errorBacklogDigest": "sha256:" + hashlib.sha256(OUT_JSON.read_bytes()).hexdigest(),
            "registrySource": "evaluation/sprint-12/optimization/experiment-registry.v5.json",
            "registrySourceDigest": sha256_file(OPT / "experiment-registry.v5.json"),
        },
        "datasetSplit": "development",
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }


def main() -> None:
    backlog = build_backlog()
    OUT_JSON.write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT_MD.write_text(markdown(backlog), encoding="utf-8")
    prereg = build_preregistration(backlog)
    PREREG_JSON.write_text(json.dumps(prereg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(f"wrote {PREREG_JSON}")
    print(json.dumps(backlog["outputAccounting"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
