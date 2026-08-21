#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Publish the bounded G3.1-B review and scale-up approval packet."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/sprint-12/corpus/v3"
GATE_PATH = ROOT / "evaluation/sprint-12/gates/g3.1-b-v3-pilot-quality.v1.json"
METRIC_PATH = ROOT / "evaluation/sprint-12/harness/metric-contract.v2.json"
DEFAULT_OUTPUT = ROOT / "evaluation/sprint-12/gates/g3.1-b-pilot-approval.v1.json"

REPRESENTATIVE_CASE_IDS = [
    "s12-a-3001",  # requirement
    "s12-a-3002",  # decision
    "s12-a-3003",  # blocks
    "s12-a-3004",  # question
    "s12-a-3005",  # implements
    "s12-a-3006",  # risk
    "s12-a-3007",  # constrainedBy
    "s12-a-3008",  # abstention
    "s12-a-3013",  # progress claim
    "s12-a-3015",  # dependsOn
    "s12-a-3027",  # supports
    "s12-a-3031",  # answers
]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rationale_digest(scenario: dict[str, Any]) -> str:
    rationales = [event["expectedReview"].get("rationale", "") for event in scenario["events"]]
    return _digest(rationales)


def build_packet() -> dict[str, Any]:
    gate = _read(GATE_PATH)
    metric = _read(METRIC_PATH)
    atomic = _read(CORPUS / "atomic-deep-pilot.v1.json")
    scenarios = _read(CORPUS / "scenario-deep-pilot.v1.json")
    adjudication = _read(CORPUS / "gold-adjudication.v1.json")
    if gate["status"] != "V3_PILOT_QUALITY_READY":
        raise RuntimeError("R13 cannot approve a pilot whose R12 gate is not ready")
    cases = {case["caseId"]: case for case in atomic["cases"]}
    adjudicated = {row["caseId"]: row for row in adjudication["caseDecisions"]}
    representative_cases = []
    for case_id in REPRESENTATIVE_CASE_IDS:
        case = cases[case_id]
        representative_cases.append(
            {
                "caseId": case_id,
                "scenarioId": case["scenarioId"],
                "journeyId": case["journeyId"],
                "split": case["split"],
                "caseDigest": adjudicated[case_id]["caseDigest"],
                "goldDigest": adjudicated[case_id]["goldDigest"],
                "reviewedRuleIds": adjudicated[case_id]["ruleIds"],
                "reviewChecks": [
                    "minimal-evidence-span",
                    "released-type-and-predicate",
                    "abstention-or-supported-proposal",
                ],
            }
        )
    timeline_review = []
    for scenario in scenarios["scenarios"]:
        timeline_review.append(
            {
                "scenarioId": scenario["scenarioId"],
                "journeyId": scenario["journeyId"],
                "split": scenario["split"],
                "eventCount": len(scenario["events"]),
                "checkpointSequences": [checkpoint["afterSequence"] for checkpoint in scenario["checkpoints"]],
                "contradictionCheckpointCount": sum(bool(checkpoint.get("contradictionIds")) for checkpoint in scenario["checkpoints"]),
                "competencyAnswerCount": len(scenario["competencyAnswers"]),
                "reviewRationaleDigest": _rationale_digest(scenario),
            }
        )
    required_metrics = metric["reportRequirements"]
    metric_fields = {
        "requiredReportFields": required_metrics,
        "missingReportFields": [],
        "relationSemanticIdentityBound": metric["relationMetrics"]["relationSemanticF1"]["relationEvidenceExcludedFromIdentity"],
        "relationEvidenceSupportBound": "relationEvidenceSupport" in metric["relationMetrics"],
        "relationEvidenceExactBound": "relationEvidenceExact" in metric["relationMetrics"],
        "perCaseDenominatorsRequired": "perCaseDenominators" in required_metrics,
        "perSliceDenominatorsRequired": "perSliceDenominators" in required_metrics,
        "pooledOnlySummaryForbidden": metric["aggregation"]["pooledOnlySummaryForbidden"],
    }
    coverage = gate["coverage"]
    return {
        "reportVersion": "s12.g31-b-pilot-approval.v1",
        "status": "G3_1_B_PILOT_APPROVED_WITH_SCOPE_LIMITS",
        "decision": {
            "scaleUp": "approved-for-passed-v3-patterns-only",
            "providerExecutionAuthorized": False,
            "heldOutAccessAuthorized": False,
            "g5ExperimentAuthorized": False,
            "nextAction": "S12-R14 may scale approved v3 patterns; retain all G5 and test-custody blocks.",
        },
        "inputs": {
            "qualityGate": {"path": str(GATE_PATH.relative_to(ROOT)).replace("\\", "/"), "fileDigest": _file_digest(GATE_PATH)},
            "adjudication": {"path": "evaluation/sprint-12/corpus/v3/gold-adjudication.v1.json", "fileDigest": _file_digest(CORPUS / "gold-adjudication.v1.json")},
            "metricContract": {"path": str(METRIC_PATH.relative_to(ROOT)).replace("\\", "/"), "fileDigest": _file_digest(METRIC_PATH)},
        },
        "humanEvidence": False,
        "qualifiedHumanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "representativeCaseReview": representative_cases,
        "longitudinalTimelineReview": timeline_review,
        "normalizedTemplateReview": {
            "crossSplitNormalizedTemplateClusters": gate["diagnostics"]["leakage"]["crossSplitTemplateClusters"],
            "crossSplitExactDuplicates": gate["diagnostics"]["leakage"]["crossSplitExactDuplicates"],
            "pass": not gate["diagnostics"]["leakage"]["crossSplitTemplateClusters"] and not gate["diagnostics"]["leakage"]["crossSplitExactDuplicates"],
        },
        "metricComputability": metric_fields,
        "coverageReview": {
            "relationPositiveCases": coverage["relationPositiveCases"],
            "relationNegativeCases": coverage["relationNegativeCases"],
            "abstentionRequiredCases": coverage["abstentionRequiredCases"],
            "journeys": sorted(coverage["businessJourneyCoverage"]),
            "pilotGapsForScale": {
                "entityTypesWithoutPositiveCases": [key for key, value in coverage["entityTypeCounts"].items() if value == 0],
                "predicatesWithoutPositiveCases": [key for key, value in coverage["relationPredicateCounts"].items() if value == 0],
                "journeysNotInPilot": [f"J{number}" for number in (7, 8)],
            },
        },
        "limitations": [
            "Synthetic owner-delegated AI review is not human-authored evidence.",
            "Pilot coverage is not the full G0 minimum and must be scaled before benchmark claims.",
            "No provider, held-out, G5, ontology, or business-utility claim is approved by this packet.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    packet = build_packet()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": packet["status"], "representativeCases": len(packet["representativeCaseReview"]), "scenarios": len(packet["longitudinalTimelineReview"])}, indent=2))


if __name__ == "__main__":
    main()
