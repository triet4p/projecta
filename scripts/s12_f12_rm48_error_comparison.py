"""Build the RM-48 offline v6/v9 error comparison.

The comparison is deliberately descriptive.  It reads only the two immutable,
sanitized Stage-A reports and emits finite counts, case-run identifiers and
registered metrics.  It never loads provider payloads, source text or runtime
execution data, and it does not authorize a remediation or a new lineage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
V9 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm48-error-comparison.v1.json"

V6_DIGEST = "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
V9_DIGEST = "sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e"
ARMS = ("predicted-entities", "gold-entities", "gold-relations")
STAGES = ("stage1", "stage2")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _report(path: Path, expected_digest: str) -> dict[str, Any]:
    if digest(path) != expected_digest:
        raise RuntimeError(f"immutable report digest mismatch: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("accounting", {}).get("providerCallsAttempted") != 144:
        raise RuntimeError("comparison requires the complete 144-call report")
    if report.get("accounting", {}).get("retryCount") != 0:
        raise RuntimeError("comparison requires zero-retry reports")
    return report


def _case_run(case: dict[str, Any]) -> str:
    return f"{case['caseId']}#run-{case['runId']}"


def _schema_failures(report: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for case in report["caseRecords"]:
        for arm in ARMS:
            data = case["arms"][arm]
            for stage in STAGES:
                value = data.get(stage)
                # Non-applicable stages in the gold arms have no response and
                # schemaValid=false; only an explicit failureClass is a failure.
                if isinstance(value, dict) and value.get("failureClass"):
                    result.setdefault(f"{arm}/{stage}", []).append(_case_run(case))
    return result


def _evidence_failures(report: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for case in report["caseRecords"]:
        for arm in ARMS:
            value = case["arms"][arm].get("invalidEvidenceCount", 0)
            if value:
                result.setdefault(arm, []).extend([_case_run(case)] * value)
    return result


def _counter_delta(old: Counter[str], new: Counter[str]) -> dict[str, int]:
    keys = sorted(set(old) | set(new))
    return {key: new[key] - old[key] for key in keys if new[key] != old[key]}


def _cluster(old: dict[str, list[str]], new: dict[str, list[str]]) -> dict[str, Any]:
    keys = sorted(set(old) | set(new))
    by_cluster: dict[str, Any] = {}
    old_all: Counter[str] = Counter(x for values in old.values() for x in values)
    new_all: Counter[str] = Counter(x for values in new.values() for x in values)
    for key in keys:
        left = set(old.get(key, ()))
        right = set(new.get(key, ()))
        by_cluster[key] = {
            "v6Count": len(old.get(key, ())),
            "v9Count": len(new.get(key, ())),
            "overlapCaseRuns": sorted(left & right),
            "newInV9CaseRuns": sorted(right - left),
            "resolvedFromV6CaseRuns": sorted(left - right),
        }
    return {
        "byArmStage": by_cluster,
        "overlapCaseRuns": sorted(set(old_all) & set(new_all)),
        "newInV9CaseRuns": sorted(set(new_all) - set(old_all)),
        "resolvedFromV6CaseRuns": sorted(set(old_all) - set(new_all)),
        "note": "Case-run overlap is descriptive; it does not establish provider or prompt causality.",
    }


def _diagnostic_counts(report: dict[str, Any], field: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for case in report["caseRecords"]:
        for arm in ARMS:
            counts.update(case["arms"][arm].get("diagnostics", {}).get(field, {}))
    return counts


def _slice_comparison(v6: dict[str, Any], v9: dict[str, Any]) -> list[dict[str, Any]]:
    left = {item["label"]: item for item in v6["sliceRecords"]}
    right = {item["label"]: item for item in v9["sliceRecords"]}
    output: list[dict[str, Any]] = []
    for label in left:
        if label not in right:
            raise RuntimeError(f"slice missing from v9: {label}")
        item: dict[str, Any] = {"label": label, "denominator": left[label]["denominator"], "arms": {}}
        for arm in ARMS:
            a6 = left[label]["metrics"]["arms"][arm]
            a9 = right[label]["metrics"]["arms"][arm]
            item["arms"][arm] = {
                "invalidEvidenceCount": {
                    "v6": a6["relation"].get("invalidEvidenceCount", 0),
                    "v9": a9["relation"].get("invalidEvidenceCount", 0),
                    "delta": a9["relation"].get("invalidEvidenceCount", 0)
                    - a6["relation"].get("invalidEvidenceCount", 0),
                },
                "schemaInvalidReasonCounts": {
                    "v6": a6.get("diagnostics", {}).get("schemaReasonCounts", {}),
                    "v9": a9.get("diagnostics", {}).get("schemaReasonCounts", {}),
                },
                "evidenceReasonCounts": {
                    "v6": a6.get("diagnostics", {}).get("evidenceReasonCounts", {}),
                    "v9": a9.get("diagnostics", {}).get("evidenceReasonCounts", {}),
                },
                "thresholdFailures": {
                    "v6": a6.get("thresholdFailures", []),
                    "v9": a9.get("thresholdFailures", []),
                    "newInV9": sorted(set(a9.get("thresholdFailures", [])) - set(a6.get("thresholdFailures", []))),
                    "resolvedInV9": sorted(set(a6.get("thresholdFailures", [])) - set(a9.get("thresholdFailures", []))),
                },
                "registeredMetricDelta": {
                    "entityMacroF1": _numeric_delta(a6["entity"].get("entityMacroF1"), a9["entity"].get("entityMacroF1")),
                    "entitySpanExact": _numeric_delta(a6["entity"].get("spanExact"), a9["entity"].get("spanExact")),
                    "relationSemanticMicroF1": _numeric_delta(a6["relation"]["semantic"].get("microF1"), a9["relation"]["semantic"].get("microF1")),
                    "relationSemanticMacroF1": _numeric_delta(a6["relation"]["semantic"].get("macroF1"), a9["relation"]["semantic"].get("macroF1")),
                },
            }
        output.append(item)
    return output


def _numeric_delta(left: Any, right: Any) -> Any:
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return "not-applicable"
    return right - left


def _arm_threshold_comparison(v6: dict[str, Any], v9: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in ARMS:
        a6 = v6["metrics"]["arms"][arm]
        a9 = v9["metrics"]["arms"][arm]
        left_failures = set(a6.get("thresholdFailures", []))
        right_failures = set(a9.get("thresholdFailures", []))
        result[arm] = {
            "v6ThresholdsPass": a6["thresholdsPass"],
            "v9ThresholdsPass": a9["thresholdsPass"],
            "newFailuresInV9": sorted(right_failures - left_failures),
            "resolvedInV9": sorted(left_failures - right_failures),
            "registeredMetricDelta": {
                "entityMacroF1": _numeric_delta(a6["entity"].get("entityMacroF1"), a9["entity"].get("entityMacroF1")),
                "entitySpanExact": _numeric_delta(a6["entity"].get("spanExact"), a9["entity"].get("spanExact")),
                "relationSemanticMicroF1": _numeric_delta(a6["relation"]["semantic"].get("microF1"), a9["relation"]["semantic"].get("microF1")),
                "relationSemanticMacroF1": _numeric_delta(a6["relation"]["semantic"].get("macroF1"), a9["relation"]["semantic"].get("macroF1")),
                "relationEvidenceSupport": _numeric_delta(a6["relation"]["evidence"].get("supportRate"), a9["relation"]["evidence"].get("supportRate")),
                "relationEvidenceExact": _numeric_delta(a6["relation"]["evidence"].get("exactRate"), a9["relation"]["evidence"].get("exactRate")),
            },
        }
    return result


def build_comparison(v6_path: Path = V6, v9_path: Path = V9) -> dict[str, Any]:
    v6 = _report(v6_path, V6_DIGEST)
    v9 = _report(v9_path, V9_DIGEST)
    schema6 = _schema_failures(v6)
    schema9 = _schema_failures(v9)
    evidence6 = _evidence_failures(v6)
    evidence9 = _evidence_failures(v9)
    a6, a9 = v6["accounting"], v9["accounting"]
    total_schema6 = sum(len(values) for values in schema6.values())
    total_schema9 = sum(len(values) for values in schema9.values())
    total_evidence6 = sum(len(values) for values in evidence6.values())
    total_evidence9 = sum(len(values) for values in evidence9.values())
    if (total_schema6, total_schema9, total_evidence6, total_evidence9) != (6, 5, 17, 20):
        raise RuntimeError("unexpected immutable report failure totals")

    return {
        "artifactVersion": "s12.s12-f-12.rm48-error-comparison.v1",
        "status": "OFFLINE_ERROR_COMPARISON_AND_REMEDIATION_OPTIONS_PREPARED_PENDING_RM49_OWNER_REVIEW",
        "taskId": "S12-RM-48",
        "experimentId": "S12-f-12",
        "preparedDate": "2026-08-22",
        "sources": {
            "v6": {"path": str(v6_path.relative_to(ROOT)).replace("\\", "/"), "digest": V6_DIGEST, "immutable": True, "providerCalls": a6["providerCallsAttempted"]},
            "v9": {"path": str(v9_path.relative_to(ROOT)).replace("\\", "/"), "digest": V9_DIGEST, "immutable": True, "providerCalls": a9["providerCallsAttempted"]},
        },
        "authorityBindings": {
            "rm46ExecutionTransition": {
                "path": "evaluation/sprint-12/optimization/s12-f-12-rm46-execution-transition.v1.json",
                "digest": "sha256:948a2f1aa1015e339692e113feb878949eb0a9b080174d0ef9cfabeca378ea95",
            },
            "rm47OwnerDecision": {
                "path": "evaluation/sprint-12/optimization/s12-f-12-rm47-owner-decision.v1.json",
                "digest": "sha256:bbb10126bf61fe0272c2421bc02d45af28ec9d9f4b9abb920258280385dd9ca5",
            },
            "rm47DecisionTransition": {
                "path": "evaluation/sprint-12/optimization/s12-f-12-rm47-decision-transition.v1.json",
                "digest": "sha256:262b090d8b55c46dfeb1730d1235513a57fc1db68452839f900aad2f842a76fb",
            },
            "authoritativeG5Packet": {
                "path": "evaluation/sprint-12/optimization/g5-packet.v33.rm47-closure.json",
                "digest": "sha256:a0973bfa97bab65ef763dc0b2a0397f0f1ad859c7aa59482ee4cbaa7cfcc9605",
            },
        },
        "analysisBoundary": {
            "sanitizedReportsOnly": True,
            "rawProviderPayloadIncluded": False,
            "rawSourceTextIncluded": False,
            "rawTriggerQuoteIncluded": False,
            "rawValidationDetailIncluded": False,
            "providerExecutionPerformed": False,
            "runtimeOrLineageModified": False,
            "causalityClaim": "unknown unless proven by a later governed experiment",
        },
        "accountingComparison": {
            "v6": {"providerCallsAttempted": a6["providerCallsAttempted"], "responsesReceived": a6["responsesReceived"], "schemaValidResponses": a6["schemaValidResponses"], "retryCount": a6["retryCount"], "totalCostUsd": a6["totalCostUsd"], "schemaInvalid": a6["failureClasses"]["schemaInvalid"]},
            "v9": {"providerCallsAttempted": a9["providerCallsAttempted"], "responsesReceived": a9["responsesReceived"], "schemaValidResponses": a9["schemaValidResponses"], "retryCount": a9["retryCount"], "totalCostUsd": a9["totalCostUsd"], "schemaInvalid": a9["failureClasses"]["schemaInvalid"]},
            "deltaV9MinusV6": {"providerCallsAttempted": 0, "responsesReceived": 0, "schemaValidResponses": 1, "retryCount": 0, "totalCostUsd": "0.00007200", "schemaInvalid": -1},
            "reconciled": True,
        },
        "failureComparison": {
            "schemaInvalid": {"v6Total": total_schema6, "v9Total": total_schema9, "deltaV9MinusV6": total_schema9 - total_schema6, "v6ByArmStage": {k: len(v) for k, v in sorted(schema6.items())}, "v9ByArmStage": {k: len(v) for k, v in sorted(schema9.items())}, "caseRunClusters": _cluster(schema6, schema9), "v6ReasonObservability": "historical detail unavailable", "v9ReasonCounts": {k: v for k, v in sorted(_diagnostic_counts(v9, "schemaReasonCounts").items()) if v}},
            "invalidEvidence": {"v6Total": total_evidence6, "v9Total": total_evidence9, "deltaV9MinusV6": total_evidence9 - total_evidence6, "v6ByArm": {k: len(v) for k, v in sorted(evidence6.items())}, "v9ByArm": {k: len(v) for k, v in sorted(evidence9.items())}, "caseRunClusters": _cluster(evidence6, evidence9), "v6ReasonObservability": "historical detail unavailable", "v9ReasonCounts": {k: v for k, v in sorted(_diagnostic_counts(v9, "evidenceReasonCounts").items()) if v}},
        },
        "goldRelationsControl": {
            "v6": {"integrityPass": v6["decision"]["goldRelationsIntegrityPass"], "invalidEvidence": 0, "thresholdsPass": v6["metrics"]["arms"]["gold-relations"]["thresholdsPass"]},
            "v9": {"integrityPass": v9["decision"]["goldRelationsIntegrityPass"], "invalidEvidence": 0, "thresholdsPass": v9["metrics"]["arms"]["gold-relations"]["thresholdsPass"]},
            "interpretation": "The control remains clean; this does not waive candidate hard gates or identify sole causality.",
        },
        "overallThresholdComparison": _arm_threshold_comparison(v6, v9),
        "thresholdAndSliceComparison": _slice_comparison(v6, v9),
        "interpretation": {
            "observedBehaviorChanges": ["schema-invalid total decreased 6 to 5", "invalid-evidence total increased 17 to 20", "v9 records finite reasons for 14 trigger-containment and 6 endpoint-containment failures"],
            "observabilityOrContractChanges": ["v6 did not retain finite failure reasons; v9 exposes registered sanitized reason codes", "the reason labels localize validation/materialization boundaries but do not prove provider, prompt or runtime causality"],
            "notEstablished": ["quality improvement", "candidate suitability", "business quality", "tenant readiness", "provider or prompt causality"],
        },
        "remediationOptions": [
            {"id": "A", "name": "Offline finite-diagnostic and contract hardening", "scope": "Implement only a new offline runtime/report contract that keeps closed reason allowlists, exact count reconciliation, and raw-data exclusion.", "expectedEvidence": "Deterministic fixtures prove one-to-one schema/evidence counts, unknowns fail closed, and no raw fields escape.", "risks": ["Cannot explain historical provider payloads that were not retained", "may improve observability without changing model behavior"], "offlineAcceptanceTests": ["schema validates", "all registered reason totals reconcile", "unknown reason is not pass", "raw provider/source/trigger/validation fields are absent"], "stopCriteria": ["any reconciliation mismatch", "any raw-data leak", "any inferred causal claim"], "authorization": "not authorized"},
            {"id": "B", "name": "Offline materializer/scorer parity fixture", "scope": "Build deterministic local fixtures covering trigger and endpoint containment, schema boundaries, slices, and gold-relations control; compare scorer and diagnostics without provider calls.", "expectedEvidence": "Known synthetic failures map to exactly one finite reason and preserve registered metric domains across slices.", "risks": ["Synthetic parity cannot establish external-provider behavior", "fixture drift can mask a live integration defect"], "offlineAcceptanceTests": ["case/arm/stage mapping is deterministic", "gold-relations control stays clean", "slice and threshold deltas are reproducible"], "stopCriteria": ["fixture cannot reproduce the observed boundary", "a live rerun is proposed before owner review"], "authorization": "not authorized"},
            {"id": "C", "name": "Stop provider experimentation", "scope": "Retain immutable v6/v9 evidence, close the remediation track, and require a separately approved product or research decision before any new Stage A.", "expectedEvidence": "A signed owner decision records no new lineage, no authorization, and no downstream access.", "risks": ["Leaves provider causality unresolved", "may defer potential contract improvements"], "offlineAcceptanceTests": ["reports and digests remain unchanged", "current state remains fail-closed", "no provider call or lineage artifact is issued"], "stopCriteria": ["any request for provider execution without a new owner gate"], "authorization": "not authorized"},
        ],
        "recommendation": "Prefer A followed by B only after RM-49 review; choose C if finite offline parity cannot be demonstrated without reconstructing withheld payload/source or if the next hypothesis cannot be preregistered with a measurable acceptance boundary.",
        "governance": {"offlineComparisonPrepared": True, "remediationImplementationAuthorized": False, "supersedingLineagePreparationAuthorized": False, "preregistrationIssued": False, "technicalFreezeIssued": False, "providerExecutionAuthorized": False, "newAuthorizationIssued": False, "validationAccessAuthorized": False, "heldOutAccessAuthorized": False, "stageBAuthorized": False, "candidateSelectionAuthorized": False, "promotionAuthorized": False},
        "nextGate": "S12-RM-49_OWNER_REVIEW_OFFLINE_ERROR_ANALYSIS_PREPARATION",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = build_comparison()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
