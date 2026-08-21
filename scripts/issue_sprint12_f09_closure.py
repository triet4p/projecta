#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Issue the offline S12-f-09 scoring erratum and G5 closure packet.

This script reads the immutable raw execution and run reports only.  It never
loads provider credentials, calls a provider, or overwrites an existing
artifact.
"""

from __future__ import annotations

import copy
import hashlib
import json
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sprint12_pricing import file_digest

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
RAW = OPT / "s12-f-09-relation-evidence-stage-a.v1.json"
REPAIRED = OPT / "s12-f-09-relation-evidence-stage-a.v2.json"
AUTH = OPT / "s12-f-09-authorization.v1.json"
PREREG = OPT / "s12-f-09-relation-evidence-preregistration.v1.json"
RUNS = OPT / "s12-f-09-relation-evidence-stage-a"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json"
REGISTRY_V10 = OPT / "experiment-registry.v10.json"
G5_V10 = OPT / "g5-packet.v10.json"
ERRATUM = OPT / "s12-f-09-scoring-erratum.v1.json"
ERRATUM_MD = OPT / "s12-f-09-scoring-erratum.v1.md"
REPORT_V3 = OPT / "s12-f-09-relation-evidence-stage-a.v3.json"
REGISTRY_V11 = OPT / "experiment-registry.v11.json"
G5_V11 = OPT / "g5-packet.v11.json"

REPORT_NAMES = (
    "pair-1-01-control.report.v1.json",
    "pair-1-02-candidate.report.v1.json",
    "pair-2-01-candidate.report.v1.json",
    "pair-2-02-control.report.v1.json",
    "pair-3-01-control.report.v1.json",
    "pair-3-02-candidate.report.v1.json",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def write_new(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite immutable artifact: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _failure_case_metric(case: Mapping[str, Any]) -> dict[str, float | int]:
    relations = case.get("relations", {})
    gold = int(relations.get("gold", 0))
    predicted = int(relations.get("predicted", 0))
    return {
        "relationSemanticF1": 0.0,
        "semanticGold": gold,
        "semanticPredicted": predicted,
        "semanticTruePositive": 0,
        "evidenceSupportTruePositive": 0,
        "evidenceExactTruePositive": 0,
        "entityF1": float(case.get("entities", {}).get("f1", 0.0)),
        "hallucinationRate": float(case.get("hallucinationRate", 0.0)),
        "abstentionAccuracy": float(case.get("abstentionAccuracy", 0.0)),
    }


def case_metric(case: Mapping[str, Any]) -> dict[str, float | int]:
    instrumentation = case.get("relationInstrumentation")
    if (
        not isinstance(instrumentation, dict)
        or instrumentation.get("status") != "scored"
    ):
        return _failure_case_metric(case)
    totals = instrumentation.get("totals", {})
    gold = int(totals.get("gold", 0))
    predicted = int(totals.get("predicted", 0))
    semantic_tp = int(totals.get("exactMatch", 0)) + int(totals.get("wrongSpan", 0))
    return {
        "relationSemanticF1": 2 * semantic_tp / (gold + predicted)
        if gold + predicted
        else 0.0,
        "semanticGold": gold,
        "semanticPredicted": predicted,
        "semanticTruePositive": semantic_tp,
        "evidenceSupportTruePositive": semantic_tp,
        "evidenceExactTruePositive": int(totals.get("exactMatch", 0)),
        "entityF1": float(case.get("entities", {}).get("f1", 0.0)),
        "hallucinationRate": float(case.get("hallucinationRate", 0.0)),
        "abstentionAccuracy": float(case.get("abstentionAccuracy", 0.0)),
    }


def _f1(tp: int, predicted: int, gold: int) -> float:
    if not gold and not predicted:
        return 1.0
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _abstention_counts(
    rows: list[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, int | float]:
    tp = fp = fn = tn = 0
    for case, gold in rows:
        gold_required = bool(gold.get("abstention", {}).get("required"))
        if case.get("status") == "missing-output":
            # The provider emitted no abstention decision.  Treat the missing
            # decision as false for fail-closed diagnostic accounting; the
            # hard gate still records the missing output separately.
            predicted_required = False
        else:
            correct = float(case.get("abstentionAccuracy", 0.0)) == 1.0
            predicted_required = gold_required if correct else not gold_required
        if gold_required and predicted_required:
            tp += 1
        elif not gold_required and predicted_required:
            fp += 1
        elif gold_required:
            fn += 1
        else:
            tn += 1
    return {
        "truePositive": tp,
        "falsePositive": fp,
        "falseNegative": fn,
        "trueNegative": tn,
        "f1": _f1(tp, tp + fp, tp + fn),
    }


def _aggregate(
    cases: list[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = [case_metric(case) for case, _gold in cases]
    gold = sum(int(row["semanticGold"]) for row in rows)
    predicted = sum(int(row["semanticPredicted"]) for row in rows)
    semantic_tp = sum(int(row["semanticTruePositive"]) for row in rows)
    support_tp = sum(int(row["evidenceSupportTruePositive"]) for row in rows)
    exact_tp = sum(int(row["evidenceExactTruePositive"]) for row in rows)
    abstention = _abstention_counts(cases)
    positive_rows = [row for row in rows if int(row["semanticGold"]) > 0]
    return {
        "caseRuns": len(rows),
        "relationPositiveCaseRuns": len(positive_rows),
        "validCaseRuns": sum(
            1 for case, _gold in cases if case.get("status") != "missing-output"
        ),
        "relationSemanticMacroF1": statistics.fmean(
            float(row["relationSemanticF1"]) for row in positive_rows
        )
        if positive_rows
        else 0.0,
        "relationSemanticMicroF1": 2 * semantic_tp / (gold + predicted)
        if gold + predicted
        else 0.0,
        "relationEvidenceSupport": support_tp / semantic_tp if semantic_tp else 0.0,
        "relationEvidenceExact": exact_tp / semantic_tp if semantic_tp else 0.0,
        "relationSemanticGold": gold,
        "relationSemanticPredicted": predicted,
        "relationSemanticTruePositive": semantic_tp,
        "relationEvidenceSupportTruePositive": support_tp,
        "relationEvidenceExactTruePositive": exact_tp,
        "entityMacroF1": statistics.fmean(float(row["entityF1"]) for row in rows)
        if rows
        else 0.0,
        "abstentionF1": float(abstention["f1"]),
        "abstentionCounts": abstention,
        "abstentionAccuracy": statistics.fmean(
            float(row["abstentionAccuracy"]) for row in rows
        )
        if rows
        else 0.0,
        "hallucinationRate": statistics.fmean(
            float(row["hallucinationRate"]) for row in rows
        )
        if rows
        else 0.0,
    }


def _run_cases(
    run: Mapping[str, Any], gold_by_id: Mapping[str, Mapping[str, Any]]
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    per_case = run.get("perCase")
    if not isinstance(per_case, dict):
        metrics = run.get("metrics", {})
        per_case = metrics.get("perCase", {}) if isinstance(metrics, dict) else {}
    return [
        (case, gold_by_id[case_id])
        for case_id, case in per_case.items()
        if case_id in gold_by_id
    ]


def _slice_labels(gold: Mapping[str, Any]) -> tuple[str, ...]:
    labels = ["all"]
    labels.append("relation-positive" if gold.get("relations") else "relation-negative")
    labels.append(
        "abstention-required"
        if gold.get("abstention", {}).get("required") is True
        else "abstention-not-required"
    )
    return tuple(labels)


def _slice_metrics(
    runs: list[Mapping[str, Any]], gold_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    grouped: dict[str, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    for run in runs:
        for case, gold in _run_cases(run, gold_by_id):
            for label in _slice_labels(gold):
                grouped.setdefault(label, []).append((case, gold))
    return {label: _aggregate(cases) for label, cases in sorted(grouped.items())}


def _stability(
    runs: list[Mapping[str, Any]], gold_by_id: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    output = []
    for run in runs:
        metrics = _aggregate(_run_cases(run, gold_by_id))
        output.append(
            {
                "runId": run.get("runId"),
                "pairId": run.get("pairId"),
                "runNumber": run.get("runNumber"),
                "caseRuns": metrics["caseRuns"],
                "validCaseRuns": metrics["validCaseRuns"],
                "failureCount": int(run.get("failureCount", 0)),
                "missingOutputCount": int(run.get("missingOutputCount", 0)),
                "relationSemanticGold": metrics["relationSemanticGold"],
                "relationSemanticPredicted": metrics["relationSemanticPredicted"],
                "relationSemanticTruePositive": metrics["relationSemanticTruePositive"],
                "relationSemanticMicroF1": metrics["relationSemanticMicroF1"],
                "relationEvidenceSupport": metrics["relationEvidenceSupport"],
                "relationEvidenceExact": metrics["relationEvidenceExact"],
                "costUsd": run.get("costUsd"),
            }
        )
    return output


def _hard_gate(runs: list[Mapping[str, Any]]) -> bool:
    return all(
        int(run.get("failureCount", 0)) == 0
        and int(run.get("missingOutputCount", 0)) == 0
        for run in runs
    )


def _report_digests() -> list[dict[str, str]]:
    return [
        {
            "artifact": (RUNS / name).relative_to(ROOT).as_posix(),
            "digest": file_digest(RUNS / name),
        }
        for name in REPORT_NAMES
    ]


def build_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    raw = read_json(RAW)
    atomic = read_json(ATOMIC)
    gold_by_id = {
        str(case["caseId"]): case["gold"]
        for case in atomic["cases"]
        if case.get("split") == "development"
        and case.get("caseId") in set(raw["caseIds"])
    }

    def load_run(name: str) -> dict[str, Any]:
        run = read_json(RUNS / name)
        run["runId"] = name.removesuffix(".report.v1.json")
        run["pairId"] = name.split("-")[0] + "-" + name.split("-")[1]
        run["runNumber"] = int(name.split("-")[1])
        return run

    control_runs = [load_run(name) for name in REPORT_NAMES if "-control." in name]
    candidate_runs = [load_run(name) for name in REPORT_NAMES if "-candidate." in name]
    control = _aggregate(
        [pair for run in control_runs for pair in _run_cases(run, gold_by_id)]
    )
    candidate = _aggregate(
        [pair for run in candidate_runs for pair in _run_cases(run, gold_by_id)]
    )
    raw_candidate = raw["candidate"]
    gates = {
        "candidateHardGate": _hard_gate(candidate_runs),
        "controlHardGate": _hard_gate(control_runs),
        "candidateRelationSemanticMacroF1Minimum": candidate["relationSemanticMacroF1"]
        >= 0.8,
        "candidateRelationSemanticMicroF1Minimum": candidate["relationSemanticMicroF1"]
        >= 0.8,
        "candidateRelationEvidenceSupportMinimum": candidate["relationEvidenceSupport"]
        >= 0.85,
        "candidateRelationEvidenceExactMinimum": candidate["relationEvidenceExact"]
        >= 0.85,
        "candidateEntityMacroF1Minimum": candidate["entityMacroF1"] >= 0.85,
        "candidateAbstentionF1Minimum": candidate["abstentionF1"] >= 0.9,
        "candidateHallucinationRateMaximum": candidate["hallucinationRate"] <= 0.05,
        "sliceFloorRequired": False,
        "supersessionFalsePositiveZero": int(
            raw_candidate.get("supersessionFalsePositiveCount", 0)
        )
        == 0,
    }
    report = {
        "artifactVersion": "s12.s12-f-09.relation-evidence-stage-a.v3",
        "experimentId": raw["experimentId"],
        "status": "STAGE_A_COMPLETED_OFFLINE_ERRATUM",
        "decision": "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B",
        "stageATechnicalPass": False,
        "stageBAuthorized": False,
        "caseCount": raw["caseCount"],
        "executionCount": raw["executionCount"],
        "attemptedCaseRuns": raw["executionCount"],
        "rawExecutionArtifact": {
            "path": RAW.relative_to(ROOT).as_posix(),
            "digest": file_digest(RAW),
        },
        "previousOfflineRepair": {
            "path": REPAIRED.relative_to(ROOT).as_posix(),
            "digest": file_digest(REPAIRED),
        },
        "control": {
            "primaryMetrics": control,
            "hardGatesPass": _hard_gate(control_runs),
            "runs": _stability(control_runs, gold_by_id),
            "sliceMetrics": _slice_metrics(control_runs, gold_by_id),
        },
        "candidate": {
            "primaryMetrics": candidate,
            "hardGatesPass": _hard_gate(candidate_runs),
            "supersessionFalsePositiveCount": int(
                raw_candidate.get("supersessionFalsePositiveCount", 0)
            ),
            "runs": _stability(candidate_runs, gold_by_id),
            "sliceMetrics": _slice_metrics(candidate_runs, gold_by_id),
        },
        "gates": gates,
        "gateContract": {
            "relationSemanticF1": {
                "preregisteredName": "relationSemanticF1Minimum",
                "preregisteredStatistic": "unspecified",
                "offlineRule": "require-both-macro-and-micro",
                "minimum": 0.8,
            },
            "abstention": {
                "preregisteredName": "abstentionF1Minimum",
                "evaluatedStatistic": "binary-positive-class-F1",
                "diagnosticAccuracyRetained": True,
            },
            "sliceFloor": {
                "requiredByPreregistration": True,
                "status": "NOT_EVALUATED_NO_VERSIONED_SLICE_THRESHOLDS",
                "gate": False,
            },
        },
        "measurement": {
            "semanticIdentityExcludesEvidenceSpan": True,
            "denominatorPolicy": "fail-closed-all-attempted-case-runs",
            "pooledEvidencePolicy": "sum-numerators-divided-by-sum-semantic-TP",
            "perCaseAndPerSliceDenominatorsPresent": True,
            "comparisonIntegrity": "DEGRADED_INDEPENDENT_STOCHASTIC_OUTPUTS",
            "toolCausalAttribution": "NOT_IDENTIFIABLE_CONTROL_AND_CANDIDATE_USED_INDEPENDENT_PROVIDER_CALLS",
            "triggerContractStatus": "NOT_EXERCISED_LIVE_PATH_TRIGGER_QUOTE_ALWAYS_OMITTED",
            "instrumentationOverlapAssessment": "NO_UNMATCHED_PREDICATE_BUCKET_PRESENT_IN_IMMUTABLE_F09_REPORTS",
        },
        "accounting": raw["accounting"],
        "executionAccounting": {
            "attemptedCaseRuns": raw["executionCount"],
            "validCaseRuns": {
                "control": control["validCaseRuns"],
                "candidate": candidate["validCaseRuns"],
            },
            "failureExplicit": True,
            "retryCount": 0,
        },
        "reportDigests": _report_digests(),
        "authorizationDigest": file_digest(AUTH),
        "preregistrationDigest": file_digest(PREREG),
        "heldOutInspected": False,
        "rawSensitiveDataIncluded": False,
        "retryCount": 0,
        "authorizationCommitLimitation": {
            "commitSha": read_json(AUTH).get("commitSha"),
            "commitContainsExecutionPackage": False,
            "status": "HISTORICAL_AUTHORIZATION_METADATA_NOT_FROZEN_EXECUTION_PACKAGE",
            "evidenceIntegrity": "PRESERVED_BY_ARTIFACT_DIGESTS",
        },
    }
    erratum = {
        "artifactVersion": "s12.s12-f-09.scoring-erratum.v1",
        "experimentId": "s12-f-09",
        "status": "ERRATUM_ISSUED_WITHOUT_RERUN",
        "decisionUnchanged": True,
        "immutableInputs": {
            "rawExecution": {
                "path": RAW.relative_to(ROOT).as_posix(),
                "digest": file_digest(RAW),
            },
            "stageARepairV2": {
                "path": REPAIRED.relative_to(ROOT).as_posix(),
                "digest": file_digest(REPAIRED),
            },
            "authorization": {
                "path": AUTH.relative_to(ROOT).as_posix(),
                "digest": file_digest(AUTH),
            },
            "runReports": _report_digests(),
        },
        "corrections": [
            "Use fail-closed gold relation denominators for missing-output records.",
            "Use pooled support and exact numerators divided by pooled semantic true positives.",
            "Use preregistered abstentionF1 naming; retain abstentionAccuracy as diagnostic only.",
            "Require both macro and micro relation semantic floors because the preregistration did not specify the statistic.",
            "Do not infer slice-floor passage when thresholds were not versioned before execution.",
        ],
        "comparisonIntegrity": "DEGRADED_INDEPENDENT_STOCHASTIC_OUTPUTS",
        "toolCausalLimitation": "The six runs cannot isolate the materializer effect because both arms made independent provider calls; a future tool comparison must branch one captured provider response through both post-processing paths.",
        "triggerLimitation": "The live candidate path passed no trigger quote, so required-trigger fail-closed behavior was not exercised.",
        "instrumentationLimitation": "The immutable f09 reports contain no unmatchedPredicate bucket; future decomposition must keep wrong-span and predicted-side unmatched categories explicitly disjoint or label overlap.",
        "metrics": {
            "control": control,
            "candidate": candidate,
        },
        "evidenceDenominator": {
            "candidateSemanticPositiveCaseRuns": candidate["relationPositiveCaseRuns"],
            "controlSemanticPositiveCaseRuns": control["relationPositiveCaseRuns"],
            "candidateEvidenceSupport": f"{candidate['relationEvidenceSupportTruePositive']}/{candidate['relationSemanticTruePositive']}",
            "controlEvidenceSupport": f"{control['relationEvidenceSupportTruePositive']}/{control['relationSemanticTruePositive']}",
            "candidateEvidenceExact": f"{candidate['relationEvidenceExactTruePositive']}/{candidate['relationSemanticTruePositive']}",
            "controlEvidenceExact": f"{control['relationEvidenceExactTruePositive']}/{control['relationSemanticTruePositive']}",
        },
        "noProviderRerun": True,
    }
    return report, erratum


def _registry_experiment(
    report: Mapping[str, Any], erratum: Mapping[str, Any]
) -> dict[str, Any]:
    prereg_digest = file_digest(PREREG)
    auth_digest = file_digest(AUTH)
    report_digests = report["reportDigests"]
    return {
        "experimentId": "s12-f-09",
        "dimension": "tool",
        "datasetVersion": "s12.corpus.atomic.v3.frozen",
        "datasetManifestDigest": file_digest(MANIFEST),
        "changedArtifacts": ["tool"],
        "hypothesis": "A server-owned deterministic relation evidence materializer improves evidence support/exactness without changing the model, prompt, sampling, dataset, evaluator or ontology.",
        "permittedSplit": "development",
        "preservedArtifacts": [
            "dataset",
            "evaluator",
            "ontology",
            "policy",
            "review-contract",
            "model",
            "prompt",
            "sampling",
        ],
        "preregistration": {"artifact": PREREG.name, "digest": prereg_digest},
        "authorization": {
            "artifact": AUTH.name,
            "digest": auth_digest,
            "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        },
        "executionPackage": read_json(AUTH).get("executionPackage", {}),
        "executionEvidence": {
            "rawAggregate": {"artifact": RAW.name, "digest": file_digest(RAW)},
            "offlineRepairV2": {
                "artifact": REPAIRED.name,
                "digest": file_digest(REPAIRED),
            },
            "offlineErratum": {
                "artifact": ERRATUM.name,
                "digest": file_digest(ERRATUM),
            },
            "correctedAggregate": {
                "artifact": REPORT_V3.name,
                "digest": file_digest(REPORT_V3),
            },
            "reports": report_digests,
            "executionCount": 288,
            "attemptedCaseRuns": 288,
            "validCaseRuns": {"control": 136, "candidate": 141},
            "decision": "REJECTED_NO_STAGE_B_NO_SELECTION",
            "comparisonIntegrity": report["measurement"]["comparisonIntegrity"],
            "authorizationCommitPackageStatus": report["authorizationCommitLimitation"][
                "status"
            ],
        },
        "measurementContract": {
            "runtimeEvaluatorVersion": "s12.evaluator.v4",
            "offlineScoringRevision": "s12.s12-f-09.relation-evidence-stage-a.v3",
            "denominator": report["measurement"]["denominatorPolicy"],
            "positiveEvidenceAggregation": report["measurement"][
                "pooledEvidencePolicy"
            ],
            "sliceFloorStatus": report["gateContract"]["sliceFloor"]["status"],
        },
        "pricingContract": {
            "artifact": "s12-f-08-pricing-deepseek-v4-flash.v1.json",
            "digest": raw_pricing_digest(),
            "status": "BOUND_FOR_COMPLETED_RUN",
        },
        "noStageB": True,
        "noCandidateSelection": True,
        "status": "COMPLETED_REJECTED",
    }


def raw_pricing_digest() -> str:
    return read_json(RAW)["accounting"]["pricingArtifactDigest"]


def build_registry(
    report: Mapping[str, Any], erratum: Mapping[str, Any]
) -> dict[str, Any]:
    registry = copy.deepcopy(read_json(REGISTRY_V10))
    registry["registryVersion"] = "s12.experiment-registry.v11"
    registry["evaluatorVersion"] = "s12.evaluator.v4"
    registry["experiments"].append(_registry_experiment(report, erratum))
    registry["openedExperimentId"] = "s12-f-09"
    registry["pendingExperiment"] = {
        "experimentId": "s12-f-09",
        "status": "COMPLETED_REJECTED",
        "executionAuthorized": False,
        "stageBAuthorized": False,
        "aggregateArtifact": REPORT_V3.name,
        "aggregateDigest": file_digest(REPORT_V3),
        "authorizationArtifact": AUTH.name,
        "authorizationDigest": file_digest(AUTH),
    }
    registry["selection"] = {
        "status": "NO_SELECTION",
        "heldOutInspected": False,
        "reason": "S12-f-09 failed hard and registered semantic gates; independent provider outputs also degrade tool causal attribution. No Stage B or candidate selection is authorized.",
    }
    registry["status"] = "G5_PREPARATION_DEVELOPMENT_CLOSED_S12_F09_REJECTED"
    registry.pop("registryDigest", None)
    registry["registryDigest"] = canonical_digest(registry)
    return registry


def build_g5(
    registry: Mapping[str, Any], report: Mapping[str, Any], erratum: Mapping[str, Any]
) -> dict[str, Any]:
    packet = copy.deepcopy(read_json(G5_V10))
    packet["packetVersion"] = "s12.g5.packet.v11"
    packet["registryVersion"] = "s12.experiment-registry.v11"
    packet["registryDigest"] = str(registry["registryDigest"])
    packet["status"] = "G5_PREPARATION_DEVELOPMENT_CLOSED_S12_F09_REJECTED"
    packet["approvalStatus"] = "COMPLETED_REJECTED_NO_STAGE_B"
    packet["pendingExperiment"] = {
        "experimentId": "s12-f-09",
        "status": "COMPLETED_REJECTED",
        "executionAuthorized": False,
        "stageBAuthorized": False,
        "aggregateArtifact": REPORT_V3.name,
        "aggregateDigest": file_digest(REPORT_V3),
    }
    packet["completedExperiment"] = {
        "experimentId": "s12-f-09",
        "aggregateArtifact": REPORT_V3.name,
        "aggregateDigest": file_digest(REPORT_V3),
        "rawAggregateArtifact": RAW.name,
        "rawAggregateDigest": file_digest(RAW),
        "offlineRepairV2Artifact": REPAIRED.name,
        "offlineRepairV2Digest": file_digest(REPAIRED),
        "offlineErratumArtifact": ERRATUM.name,
        "offlineErratumDigest": file_digest(ERRATUM),
        "authorizationArtifact": AUTH.name,
        "authorizationDigest": file_digest(AUTH),
        "reports": report["reportDigests"],
        "accounting": report["accounting"],
        "noStageB": True,
        "noCandidateSelection": True,
        "status": "COMPLETED_REJECTED",
    }
    packet["closedExperiment"] = packet["completedExperiment"]
    packet["selection"] = {
        "status": "NO_SELECTION",
        "heldOutInspected": False,
        "reason": "S12-f-09 rejected; no candidate is available.",
    }
    packet["executionBlockedReasons"] = [
        "S12-f-09 failed hard and registered semantic gates",
        "comparison integrity is degraded by independent stochastic provider outputs",
        "no Stage B or candidate selection is authorized",
        "immutable raw and run reports are preserved",
    ]
    packet["registryDigest"] = str(registry["registryDigest"])
    return packet


def write_markdown(report: Mapping[str, Any], erratum: Mapping[str, Any]) -> None:
    lines = [
        "# S12-f-09 scoring erratum",
        "",
        "Status: `ERRATUM_ISSUED_WITHOUT_RERUN`.",
        "",
        "The raw six-run aggregate, repaired v2 report, and all six run reports remain immutable. This erratum is offline-only and does not authorize Stage B or candidate selection.",
        "",
        "## Corrected contract",
        "",
        "- Missing outputs retain the gold relation denominator and receive zero relation true positives.",
        "- Evidence support/exact are pooled ratios: summed numerator divided by summed semantic true positives.",
        "- The preregistered `abstentionF1Minimum` is evaluated as binary positive-class F1; accuracy is diagnostic only.",
        "- Relation semantic floor is checked for both macro and micro because the preregistration did not specify which statistic it meant.",
        "- The required slice floor is `NOT_EVALUATED` because no versioned slice thresholds were bound before execution; therefore it cannot pass.",
        "",
        "## Corrected evidence",
        "",
        f"- Control valid case-runs: `{report['control']['primaryMetrics']['validCaseRuns']}/144`; candidate: `{report['candidate']['primaryMetrics']['validCaseRuns']}/144`.",
        f"- Control semantic micro F1: `{report['control']['primaryMetrics']['relationSemanticMicroF1']:.6f}`; candidate: `{report['candidate']['primaryMetrics']['relationSemanticMicroF1']:.6f}`.",
        f"- Evidence support: control `{erratum['evidenceDenominator']['controlEvidenceSupport']}`, candidate `{erratum['evidenceDenominator']['candidateEvidenceSupport']}`.",
        f"- Evidence exact: control `{erratum['evidenceDenominator']['controlEvidenceExact']}`, candidate `{erratum['evidenceDenominator']['candidateEvidenceExact']}`.",
        "",
        "## Limitations",
        "",
        "- Comparison integrity is `DEGRADED_INDEPENDENT_STOCHASTIC_OUTPUTS`: the two arms did not branch one captured provider response.",
        "- The live candidate path omitted the optional trigger quote, so the required-trigger fail-closed path was not exercised.",
        "- The immutable reports contain no `unmatchedPredicate` bucket; future instrumentation must make any predicted-side overlap explicit.",
        "- The authorization commit did not contain the complete f09 execution package; artifact digests preserve evidence integrity but do not retroactively create a frozen commit.",
        "",
        "Decision: `COMPLETED_REJECTED_NO_STAGE_B_NO_SELECTION`.",
        "",
    ]
    if ERRATUM_MD.exists():
        raise SystemExit(f"refusing to overwrite immutable artifact: {ERRATUM_MD}")
    ERRATUM_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    report, erratum = build_artifacts()
    write_new(REPORT_V3, report)
    write_new(ERRATUM, erratum)
    write_markdown(report, erratum)
    registry = build_registry(report, erratum)
    write_new(REGISTRY_V11, registry)
    packet = build_g5(registry, report, erratum)
    write_new(G5_V11, packet)
    print(
        json.dumps(
            {
                "status": report["status"],
                "decision": report["decision"],
                "executionCount": report["executionCount"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
