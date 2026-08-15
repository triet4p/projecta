"""Close rejected S12-f-07 evidence and prepare, but do not execute, S12-f-08."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PREREG_F07 = OPT / "s12-f-07-relation-prompt-preregistration.v2.json"
AGGREGATE_F07 = OPT / "s12-f-07-relation-prompt-stage-a.v1.json"
REPORT_DIR_F07 = OPT / "s12-f-07-relation-prompt-stage-a"
REGISTRY_V7 = OPT / "experiment-registry.v7.json"
G5_V7 = OPT / "g5-packet.v7.json"
PROMPT_V5 = OPT / "s12-f-08-prompt-v5-composed-relation-contract.v1.txt"
ERRATUM = OPT / "s12-f-07-scoring-erratum.v1.json"
ERRATUM_MD = OPT / "s12-f-07-scoring-erratum.v1.md"
PREREG_F08 = OPT / "s12-f-08-relation-prompt-preregistration.v1.json"
AUTH_F08 = OPT / "s12-f-08-authorization.v1.json"
REGISTRY_V8 = OPT / "experiment-registry.v8.json"
G5_V8 = OPT / "g5-packet.v8.json"
G5_MD_V8 = ROOT / "docs/sprint-plans/sprint-12/g5-optimization.v8.md"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/atomic-development-validation.v2.json"
MANIFEST = ROOT / "evaluation/sprint-12/corpus/manifests/development-validation.manifest.v2.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: object) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite immutable/new artifact: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def report_rows(aggregate: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    rows = []
    for arm in ("control", "candidate"):
        for run in aggregate[arm]["runs"]:
            path = ROOT / run["reportPath"]
            rows.append((arm, run, load(path)))
    return rows


def case_metric(case: dict[str, Any], field: str) -> float:
    if case.get("status") != "scored":
        return 0.0
    return float(case.get(field, {}).get("f1", 0.0))


def corrected_metrics(aggregate: dict[str, Any]) -> dict[str, Any]:
    dataset = load(ATOMIC)
    manifest = load(MANIFEST)
    by_id = {str(case["caseId"]): case for case in dataset["cases"]}
    manifest_by_id = {str(item["caseId"]): item for item in manifest["atomicCases"]}
    supersession_ids = {
        case_id
        for case_id in aggregate["protocol"]["caseIds"]
        if manifest_by_id[case_id]["slice"] == "contradiction-or-supersession"
    }
    positive_ids = {
        case_id
        for case_id in aggregate["protocol"]["caseIds"]
        if by_id[case_id]["gold"]["relations"]
    }
    output: dict[str, Any] = {}
    for arm in ("control", "candidate"):
        values = {name: [] for name in ("entityMacroF1", "relationMacroF1", "abstentionAccuracy", "hallucinationRate")}
        positive_values: list[float] = []
        positive_tp = positive_gold = positive_predicted = 0
        slice_values = {name: [] for name in ("abstentionAccuracy", "hallucinationRate")}
        slice_missing = 0
        for run in aggregate[arm]["runs"]:
            report = load(ROOT / run["reportPath"])
            for case_id, case in report["metrics"]["perCase"].items():
                values["entityMacroF1"].append(case_metric(case, "entities"))
                values["relationMacroF1"].append(case_metric(case, "relations"))
                values["abstentionAccuracy"].append(0.0 if case.get("status") != "scored" else float(case.get("abstentionAccuracy", 0.0)))
                values["hallucinationRate"].append(0.0 if case.get("status") != "scored" else float(case.get("hallucinationRate", 0.0)))
                if case_id in positive_ids:
                    relation = case.get("relations", {})
                    positive_values.append(float(relation.get("f1", 0.0)))
                    positive_tp += int(relation.get("truePositive", 0))
                    positive_gold += int(relation.get("gold", 0))
                    positive_predicted += int(relation.get("predicted", 0))
                if case_id in supersession_ids:
                    slice_values["abstentionAccuracy"].append(values["abstentionAccuracy"][-1])
                    slice_values["hallucinationRate"].append(values["hallucinationRate"][-1])
                    slice_missing += case.get("status") != "scored"
        output[arm] = {
            name: sum(items) / len(items) if items else 0.0
            for name, items in values.items()
        }
        output[arm]["positiveRelationMacroF1"] = sum(positive_values) / len(positive_values) if positive_values else 0.0
        denominator = positive_gold + positive_predicted
        output[arm]["positiveRelationMicroF1"] = 2 * positive_tp / denominator if denominator else 1.0
        output[arm]["positiveRelationCaseRuns"] = len(positive_values)
        output[arm]["supersessionSlice"] = {
            "caseCount": len(supersession_ids),
            "caseRuns": len(slice_values["abstentionAccuracy"]),
            "abstentionAccuracy": sum(slice_values["abstentionAccuracy"]) / len(slice_values["abstentionAccuracy"]),
            "hallucinationRate": sum(slice_values["hallucinationRate"]) / len(slice_values["hallucinationRate"]),
            "missingOutputCount": slice_missing,
        }
    output["delta"] = {
        "entityMacroF1": output["candidate"]["entityMacroF1"] - output["control"]["entityMacroF1"],
        "relationMacroF1": output["candidate"]["relationMacroF1"] - output["control"]["relationMacroF1"],
        "abstentionAccuracy": output["candidate"]["abstentionAccuracy"] - output["control"]["abstentionAccuracy"],
        "hallucinationRateIncrease": output["candidate"]["hallucinationRate"] - output["control"]["hallucinationRate"],
        "positiveRelationMacroF1": output["candidate"]["positiveRelationMacroF1"] - output["control"]["positiveRelationMacroF1"],
    }
    return output


def build_erratum(aggregate: dict[str, Any]) -> dict[str, Any]:
    rows = report_rows(aggregate)
    corrected = corrected_metrics(aggregate)
    return {
        "artifactVersion": "s12.s12-f-07.scoring-erratum.v1",
        "experimentId": "s12-f-07",
        "status": "SCORING_ERRATUM_ISSUED_MEASUREMENT_LIMITATION_RETAINED",
        "immutableEvidence": True,
        "providerCallsForErratum": 0,
        "sourceAggregate": {
            "artifact": AGGREGATE_F07.name,
            "digest": file_digest(AGGREGATE_F07),
        },
        "sourceReports": [
            {"artifact": run["reportPath"], "digest": run["reportDigest"], "arm": arm}
            for arm, run, _ in rows
        ],
        "measurementCorrection": {
            "bug": "The Stage A runner looked for entityMacroF1 and relationMacroF1 in per-case records; the persisted keys are entities and relations.",
            "source": "scripts/run_sprint12_f07_prompt_experiment.py:_case_metric",
            "correctedEntityMetric": "entities.f1",
            "correctedRelationMetric": "relations.f1",
            "aggregateRewritten": False,
        },
        "correctedMetrics": corrected,
        "relationMetricStatus": "PROVISIONAL_MEASUREMENT_LIMITATION",
        "relationMetricLimitation": "The immutable reports retain sanitized scored metrics but not raw predictions; relation endpoint canonicalization cannot be fully rescored retrospectively. The current relation values are retained as provisional and do not authorize a rerun.",
        "hardGates": {
            "control": aggregate["control"]["hardGatesPass"],
            "candidate": aggregate["candidate"]["hardGatesPass"],
            "decisionPreserved": aggregate["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B",
        },
        "supersessionEvidencePreserved": True,
        "noStageB": True,
        "noCandidateSelection": True,
        "pricingStatus": aggregate["accounting"]["costAccountingStatus"],
        "heldOutInspected": False,
        "rawSensitiveDataIncluded": False,
    }


def build_f08_prereg(erratum: dict[str, Any]) -> dict[str, Any]:
    f07 = load(PREREG_F07)
    candidate = copy.deepcopy(f07["candidate"])
    candidate["configuration"]["promptVersion"] = "m3.prompt.v5.composed-relation-contract"
    candidate["configurationDigest"] = canonical_digest(candidate["configuration"])
    return {
        "artifactVersion": "s12.s12-f-08.relation-prompt-preregistration.v1",
        "experimentId": "s12-f-08",
        "status": "PREREGISTERED_NOT_EXECUTED",
        "revisionOf": None,
        "hypothesis": "A composed m3.v2 contract-aligned prompt that retains the supersession guard and adds the relation rubric will reduce supersession false positives and improve positive-relation extraction without harming entity, abstention or hallucination behavior.",
        "changedDimension": "prompt",
        "control": f07["control"],
        "candidate": candidate,
        "fixedArtifacts": copy.deepcopy(f07["fixedArtifacts"]),
        "datasetSplit": "development",
        "stageA": copy.deepcopy(f07["stageA"]),
        "denominatorContract": {
            **copy.deepcopy(f07["denominatorContract"]),
            "positiveRelationMacroF1Minimum": 0.05,
            "positiveRelationMacroF1MinimumDelta": 0.05,
            "positiveRelationMicroF1Minimum": 0.05,
            "supersessionFalsePositiveMaximum": 0,
            "supersessionSliceCaseCount": 5,
        },
        "semanticGates": {
            "entityMacroF1MaximumDecrease": 0.01,
            "abstentionAccuracyMaximumDecrease": 0.01,
            "hallucinationRateIncrease": 0.0,
            "positiveRelationMacroF1Minimum": 0.05,
            "positiveRelationMacroF1MinimumDelta": 0.05,
            "positiveRelationMicroF1Minimum": 0.05,
            "supersessionFalsePositiveMaximum": 0,
        },
        "hardGates": {
            "schema_invalid": 0,
            "invalid_evidence": 0,
            "missing_output": 0,
        },
        "costAccounting": {
            "latencyRequired": True,
            "usageRequired": True,
            "providerPriceConfigurationRequiredBeforeExecution": True,
            "providerPriceConfigurationRequiredBeforeSelection": True,
        },
        "pricingContract": {
            "requiredBeforeExecution": True,
            "requiredBeforeSelection": True,
            "status": "REQUIRED_BEFORE_EXECUTION",
            "rationale": "S12-f-08 requires a bound provider price table before any execution so the paired comparison has complete cost accounting.",
        },
        "promptArtifact": {
            "artifact": PROMPT_V5.name,
            "digest": file_digest(PROMPT_V5),
            "implementation": "apps/api/src/projecta_api/extraction/prompt.py",
            "implementationDigest": file_digest(ROOT / "apps/api/src/projecta_api/extraction/prompt.py"),
        },
        "sourceEvidence": {
            "f07Aggregate": AGGREGATE_F07.name,
            "f07AggregateDigest": file_digest(AGGREGATE_F07),
            "f07ScoringErratum": ERRATUM.name,
            "f07ScoringErratumDigest": file_digest(ERRATUM),
            "promptArtifactDigest": file_digest(PROMPT_V5),
        },
        "executionAuthorized": False,
        "executionDeferredByUserInstruction": True,
        "heldOutInspected": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
        "prohibitedBeforeStageA": ["deepseek-v4-pro", "sampling-sweep", "held-out-inspection", "gold-or-ontology-change"],
    }


def build_registry_v8(f08: dict[str, Any], erratum: dict[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(load(REGISTRY_V7))
    registry.pop("registryDigest", None)
    registry["registryVersion"] = "s12.experiment-registry.v8"
    registry["openedExperimentId"] = "s12-f-08"
    f07 = next(item for item in registry["experiments"] if item["experimentId"] == "s12-f-07")
    f07.update(
        {
            "status": "COMPLETED_REJECTED",
            "executionEvidence": {
                "aggregate": {"artifact": AGGREGATE_F07.name, "digest": file_digest(AGGREGATE_F07)},
                "reports": [
                    {"artifact": run["reportPath"], "digest": run["reportDigest"]}
                    for arm in ("control", "candidate")
                    for run in load(AGGREGATE_F07)[arm]["runs"]
                ],
                "scoringErratum": {"artifact": ERRATUM.name, "digest": file_digest(ERRATUM)},
                "decision": "REJECTED_NO_STAGE_B_NO_SELECTION",
            },
        }
    )
    registry["experiments"].append(
        {
            "experimentId": "s12-f-08",
            "hypothesis": f08["hypothesis"],
            "dimension": "prompt",
            "permittedSplit": "development",
            "baselineConfigurationDigest": f08["control"]["configurationDigest"],
            "candidateConfigurationDigest": f08["candidate"]["configurationDigest"],
            "datasetManifestDigest": f08["fixedArtifacts"]["datasetManifestDigest"],
            "metricTarget": {
                "positiveRelationMacroF1": {"direction": "higher", "minimumDelta": 0.05, "minimumAbsolute": 0.05},
                "positiveRelationMicroF1": {"direction": "higher", "minimumAbsolute": 0.05},
                "entityMacroF1": {"direction": "higher", "minimumDelta": -0.01},
                "abstentionAccuracy": {"direction": "higher", "minimumDelta": -0.01},
                "hallucinationRate": {"direction": "lower", "maximumDelta": 0.0},
                "supersessionFalsePositive": {"direction": "lower", "maximum": 0},
            },
            "stoppingRule": "Stop if candidate hard gates fail or supersession false positives exceed zero; authorize no Stage B until positive-relation floors/deltas, non-inferiority and bound pricing pass.",
            "changedArtifacts": ["prompt"],
            "preservedArtifacts": ["dataset", "evaluator", "ontology", "policy", "review-contract", "context", "tool"],
            "status": "REGISTERED_PENDING_AUTHORIZATION",
            "preregistration": {"artifact": PREREG_F08.name, "digest": file_digest(PREREG_F08)},
            "promptArtifact": f08["promptArtifact"],
            "denominatorContract": f08["denominatorContract"],
            "pricingContract": f08["pricingContract"],
        }
    )
    registry["pendingExperiment"] = {
        "experimentId": "s12-f-08",
        "preregistration": {"artifact": PREREG_F08.name, "digest": file_digest(PREREG_F08)},
        "authorization": {"artifact": AUTH_F08.name, "status": "PENDING_USER_AUTHORIZATION"},
        "executionAuthorized": False,
        "stageBAuthorized": False,
    }
    registry["status"] = "G5_PREPARATION_DEVELOPMENT_OPEN_S12_F08_PENDING_AUTHORIZATION"
    registry["registryDigest"] = canonical_digest(registry)
    return registry


def build_auth_f08(f08: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifactVersion": "s12.s12-f-08.authorization.v1",
        "experimentId": "s12-f-08",
        "status": "PENDING_USER_AUTHORIZATION",
        "approvalSource": "pending-owner-approval",
        "preregistration": {"artifact": PREREG_F08.name, "digest": file_digest(PREREG_F08)},
        "registry": {"artifact": REGISTRY_V8.name, "digest": registry["registryDigest"]},
        "scope": {
            "stage": "A",
            "caseCount": f08["stageA"]["caseCount"],
            "independentPairedRuns": f08["stageA"]["independentPairedRuns"],
            "developmentOnly": True,
            "heldOutInspected": False,
            "noRetryWithinEachRun": True,
            "stageBAuthorized": False,
            "validationAuthorized": False,
        },
        "pricingContract": f08["pricingContract"],
        "credentialIncluded": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }


def build_g5_v8(f08: dict[str, Any], registry: dict[str, Any], auth: dict[str, Any], erratum: dict[str, Any]) -> dict[str, Any]:
    return {
        "packetVersion": "s12.g5.packet.v8",
        "status": "G5_PREPARATION_DEVELOPMENT_OPEN_S12_F08_PENDING_AUTHORIZATION",
        "approvalStatus": "APPROVED_WITH_LIMITATIONS",
        "registryVersion": registry["registryVersion"],
        "registryDigest": registry["registryDigest"],
        "datasetVersion": f08["fixedArtifacts"]["datasetVersion"],
        "datasetManifestDigest": f08["fixedArtifacts"]["datasetManifestDigest"],
        "closedExperiment": {
            "experimentId": "s12-f-07",
            "status": "COMPLETED_REJECTED",
            "aggregateArtifact": AGGREGATE_F07.name,
            "aggregateDigest": file_digest(AGGREGATE_F07),
            "scoringErratumArtifact": ERRATUM.name,
            "scoringErratumDigest": file_digest(ERRATUM),
            "noStageB": True,
            "noCandidateSelection": True,
        },
        "pendingExperiment": {
            "experimentId": "s12-f-08",
            "preregistrationArtifact": PREREG_F08.name,
            "preregistrationDigest": file_digest(PREREG_F08),
            "authorizationArtifact": AUTH_F08.name,
            "authorizationDigest": file_digest(AUTH_F08),
            "executionAuthorized": False,
            "stageBAuthorized": False,
        },
        "denominatorContract": f08["denominatorContract"],
        "pricingContract": f08["pricingContract"],
        "candidateAvailable": False,
        "candidateFreezeAuthorized": False,
        "heldOutInspected": False,
        "validationAuthorized": False,
        "optimizationAuthorized": False,
        "selection": {"status": "NO_SELECTION", "reason": "S12-f-07 was rejected; S12-f-08 is pending authorization and pricing.", "heldOutInspected": False},
        "executionBlockedReasons": ["S12-f-08 authorization is pending", "provider pricing must be bound before execution", "S12-f-07 was rejected with no Stage B or selection"],
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }


def main() -> None:
    aggregate = load(AGGREGATE_F07)
    erratum = build_erratum(aggregate)
    write_new(ERRATUM, erratum)
    ERRATUM_MD.write_text(
        "# S12-f-07 Scoring Erratum v1\n\n"
        "S12-f-07 remains rejected and is not rerun. The aggregate artifact and six reports are immutable. The runner field-mapping defect is corrected in code, while relation metrics remain provisional because raw predictions were not retained for retrospective endpoint canonicalization.\n\n"
        f"- Aggregate: `{AGGREGATE_F07.name}` / `{file_digest(AGGREGATE_F07)}`\n"
        f"- Erratum: `{ERRATUM.name}` / `{file_digest(ERRATUM)}`\n"
        "- Decision: `REJECTED_NO_STAGE_B_NO_SELECTION`\n",
        encoding="utf-8",
    )
    f08 = build_f08_prereg(erratum)
    write_new(PREREG_F08, f08)
    registry = build_registry_v8(f08, erratum)
    write_new(REGISTRY_V8, registry)
    auth = build_auth_f08(f08, registry)
    write_new(AUTH_F08, auth)
    g5 = build_g5_v8(f08, registry, auth, erratum)
    write_new(G5_V8, g5)
    G5_MD_V8.write_text(
        "# Sprint 12 G5 Optimization Packet v8\n\n"
        "S12-f-07 is `COMPLETED_REJECTED`: its 96 executions are preserved, no Stage B or selection is allowed, and the aggregate is not overwritten. S12-f-08 is preregistered with composed prompt v5, corrected measurement contract, positive-relation gates, zero supersession false positives, and pricing required before execution.\n\n"
        f"- Registry: `{REGISTRY_V8.name}` / `{registry['registryDigest']}`\n"
        f"- Erratum: `{ERRATUM.name}` / `{file_digest(ERRATUM)}`\n"
        f"- S12-f-08 preregistration: `{PREREG_F08.name}` / `{file_digest(PREREG_F08)}`\n"
        f"- S12-f-08 authorization: `{AUTH_F08.name}` / `{file_digest(AUTH_F08)}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"closed": "s12-f-07", "opened": "s12-f-08", "registry": REGISTRY_V8.name, "g5": G5_V8.name}, sort_keys=True))


if __name__ == "__main__":
    main()
