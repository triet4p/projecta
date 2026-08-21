#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Repair only the offline aggregation of an immutable f09 Stage A run."""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sprint12_pricing import file_digest

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
RUNS = OPT / "s12-f-09-relation-evidence-stage-a"
RAW = OPT / "s12-f-09-relation-evidence-stage-a.v1.json"
AUTH = OPT / "s12-f-09-authorization.v1.json"
OUTPUT = OPT / "s12-f-09-relation-evidence-stage-a.v2.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric(case: Mapping[str, Any]) -> dict[str, Any]:
    instrumentation = case.get("relationInstrumentation")
    if (
        not isinstance(instrumentation, dict)
        or instrumentation.get("status") != "scored"
    ):
        relation_metrics = case.get("relations", {})
        return {
            "status": "not-available",
            "relationSemanticF1": 0.0,
            "relationEvidenceSupport": 0.0,
            "relationEvidenceExact": 0.0,
            "semanticGold": int(relation_metrics.get("gold", 0)),
            "semanticPredicted": int(relation_metrics.get("predicted", 0)),
            "semanticTruePositive": 0,
            "evidenceSupportTruePositive": 0,
            "evidenceExactTruePositive": 0,
        }
    totals = instrumentation.get("totals", {})
    gold = int(totals.get("gold", 0))
    predicted = int(totals.get("predicted", 0))
    semantic_tp = int(totals.get("exactMatch", 0)) + int(totals.get("wrongSpan", 0))
    exact_tp = int(totals.get("exactMatch", 0))
    support_tp = 0
    for record in instrumentation.get("signatures", {}).get("predicted", []):
        if record.get("errorClass") not in {"exactMatch", "wrongSpan"}:
            continue
        evidence = record.get("evidenceSpan", {})
        source = record.get("sourceEndpoint", {})
        target = record.get("targetEndpoint", {})
        if (
            evidence.get("status") != "missing"
            and source.get("status") == "resolved"
            and target.get("status") == "resolved"
            and evidence.get("startOffset", 0) <= source.get("startOffset", -1)
            and evidence.get("startOffset", 0) <= target.get("startOffset", -1)
            and evidence.get("endOffset", 0) >= source.get("endOffset", 0)
            and evidence.get("endOffset", 0) >= target.get("endOffset", 0)
        ):
            support_tp += 1
    return {
        "status": "scored",
        "relationSemanticF1": 2 * semantic_tp / (gold + predicted)
        if gold + predicted
        else "not-applicable",
        "relationEvidenceSupport": support_tp / semantic_tp
        if semantic_tp
        else "not-applicable",
        "relationEvidenceExact": exact_tp / semantic_tp
        if semantic_tp
        else "not-applicable",
        "semanticGold": gold,
        "semanticPredicted": predicted,
        "semanticTruePositive": semantic_tp,
        "evidenceSupportTruePositive": support_tp,
        "evidenceExactTruePositive": exact_tp,
    }


def _arm_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        _metric(case) for run in runs for case in run["metrics"]["perCase"].values()
    ]
    gold = sum(int(row["semanticGold"]) for row in rows)
    predicted = sum(int(row["semanticPredicted"]) for row in rows)
    tp = sum(int(row["semanticTruePositive"]) for row in rows)
    support_tp = sum(int(row["evidenceSupportTruePositive"]) for row in rows)
    exact_tp = sum(int(row["evidenceExactTruePositive"]) for row in rows)
    return {
        "caseRuns": len(rows),
        "relationSemanticF1": statistics.fmean(
            float(row["relationSemanticF1"]) for row in rows
        )
        if rows
        else "not-applicable",
        "relationSemanticMicroF1": 2 * tp / (gold + predicted)
        if gold + predicted
        else "not-applicable",
        "relationEvidenceSupport": support_tp / tp if tp else 0.0,
        "relationEvidenceExact": exact_tp / tp if tp else 0.0,
        "relationSemanticGold": gold,
        "relationSemanticPredicted": predicted,
        "relationSemanticTruePositive": tp,
        "relationEvidenceSupportTruePositive": support_tp,
        "relationEvidenceExactTruePositive": exact_tp,
        "entityMacroF1": statistics.fmean(
            float(case.get("entities", {}).get("f1", 0.0))
            for run in runs
            for case in run["metrics"]["perCase"].values()
        ),
        "abstentionAccuracy": statistics.fmean(
            float(case.get("abstentionAccuracy", 0.0))
            for run in runs
            for case in run["metrics"]["perCase"].values()
        ),
        "hallucinationRate": statistics.fmean(
            float(case.get("hallucinationRate", 0.0))
            for run in runs
            for case in run["metrics"]["perCase"].values()
        ),
    }


def _hard_gate(runs: list[dict[str, Any]]) -> bool:
    return all(
        int(run["failureCount"]) == 0 and int(run["missingOutputCount"]) == 0
        for run in runs
    )


def _load_arm(prefix: str) -> list[dict[str, Any]]:
    return [
        _read(RUNS / name)
        for name in sorted(
            path.name for path in RUNS.glob(f"*-{prefix}.report.v1.json")
        )
    ]


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite repaired report: {OUTPUT}")
    raw = _read(RAW)
    control_runs = _load_arm("control")
    candidate_runs = _load_arm("candidate")
    control = _arm_metrics(control_runs)
    candidate = _arm_metrics(candidate_runs)
    supersession_fp = int(raw["candidate"]["supersessionFalsePositiveCount"])
    gates = {
        "candidateHardGate": _hard_gate(candidate_runs),
        "controlHardGate": _hard_gate(control_runs),
        "candidateRelationSemanticF1": candidate["relationSemanticMicroF1"]
        != "not-applicable"
        and candidate["relationSemanticMicroF1"] >= 0.80,
        "candidateRelationEvidenceSupport": candidate["relationEvidenceSupport"]
        != "not-applicable"
        and candidate["relationEvidenceSupport"] >= 0.85,
        "candidateRelationEvidenceExact": candidate["relationEvidenceExact"]
        != "not-applicable"
        and candidate["relationEvidenceExact"] >= 0.85,
        "candidateEntityMacroF1": candidate["entityMacroF1"] >= 0.85,
        "candidateAbstentionAccuracy": candidate["abstentionAccuracy"] >= 0.90,
        "candidateHallucinationRate": candidate["hallucinationRate"] <= 0.05,
        "supersessionFalsePositiveZero": supersession_fp == 0,
    }
    report = {
        "artifactVersion": "s12.s12-f-09.relation-evidence-stage-a.v2",
        "experimentId": raw["experimentId"],
        "status": "STAGE_A_COMPLETED_OFFLINE_REPAIRED",
        "decision": "STAGE_A_ELIGIBLE_FOR_STAGE_B"
        if all(gates.values())
        else "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B",
        "stageATechnicalPass": all(gates.values()),
        "stageBAuthorized": False,
        "caseCount": raw["caseCount"],
        "executionCount": raw["executionCount"],
        "rawExecutionArtifact": {
            "path": RAW.relative_to(ROOT).as_posix(),
            "digest": file_digest(RAW),
        },
        "control": {
            "primaryMetrics": control,
            "hardGatesPass": _hard_gate(control_runs),
            "runs": raw["control"]["runs"],
        },
        "candidate": {
            "primaryMetrics": candidate,
            "hardGatesPass": _hard_gate(candidate_runs),
            "supersessionFalsePositiveCount": supersession_fp,
            "runs": raw["candidate"]["runs"],
        },
        "gates": gates,
        "accounting": raw["accounting"],
        "measurement": {
            "semanticIdentityExcludesEvidenceSpan": True,
            "evidenceZeroDenominatorPolicy": "not-applicable",
            "bucketReconciliationPassForScoredCases": all(
                run["metrics"]["perCase"][case_id]
                .get("relationInstrumentation", {})
                .get("reconciliation", {})
                .get("pass", False)
                for run in control_runs + candidate_runs
                for case_id in run["metrics"]["perCase"]
                if run["metrics"]["perCase"][case_id]
                .get("relationInstrumentation", {})
                .get("status")
                == "scored"
            ),
            "sliceFloorStatus": "NOT_EVALUATED_SLICE_LABELS_NOT_BOUND_IN_F09_PREREGISTRATION",
        },
        "authorizationDigest": file_digest(AUTH),
        "heldOutInspected": False,
        "rawSensitiveDataIncluded": False,
        "retryCount": 0,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
