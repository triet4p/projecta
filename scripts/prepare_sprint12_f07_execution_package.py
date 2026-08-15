"""Prepare the offline S12-f-07 execution package without authorizing a run."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "evaluation/sprint-12/optimization"
PREREG_V1 = OPT / "s12-f-07-relation-prompt-preregistration.v1.json"
PREREG_V2 = OPT / "s12-f-07-relation-prompt-preregistration.v2.json"
REGISTRY_V5 = OPT / "experiment-registry.v5.json"
REGISTRY_V6 = OPT / "experiment-registry.v6.json"
AUTHORIZATION = OPT / "s12-f-07-authorization.v1.json"
G5_V6 = OPT / "g5-packet.v6.json"
G5_MD_V6 = ROOT / "docs/sprint-plans/sprint-12/g5-optimization.v6.md"
PROMPT_ARTIFACT = OPT / "s12-f-07-prompt-v4-relation-decision-rubric.v1.txt"
BACKLOG = OPT / "development-error-analysis.v1.json"


def file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_preregistration() -> dict[str, Any]:
    prereg = copy.deepcopy(load(PREREG_V1))
    prereg.update(
        {
            "artifactVersion": "s12.s12-f-07.relation-prompt-preregistration.v2",
            "revisionOf": PREREG_V1.name,
            "executionAuthorized": False,
            "executionDeferredByUserInstruction": True,
            "promptArtifact": {
                "artifact": PROMPT_ARTIFACT.name,
                "digest": file_digest(PROMPT_ARTIFACT),
                "implementation": "apps/api/src/projecta_api/extraction/prompt.py",
                "implementationDigest": file_digest(
                    ROOT / "apps/api/src/projecta_api/extraction/prompt.py"
                ),
            },
            "pricingContract": {
                "requiredBeforeExecution": False,
                "requiredBeforeSelection": True,
                "status": "NOT_BOUND_PRESELECTION",
                "rationale": "Stage A may produce development evidence without a bound price table; candidate selection, Stage B authorization and any promotion remain blocked until the provider price configuration is bound and cost is recomputed.",
            },
            "denominatorContract": {
                "primary": {
                    "name": "fail_closed_all_declared_case_runs",
                    "caseRunsPerArm": 48,
                    "missingOutputTreatment": "metric_value_zero_and_hard_gate_failure_for_that_arm",
                },
                "sensitivity": {
                    "name": "paired_common_valid_case_runs",
                    "missingOutputTreatment": "exclude_only_from_sensitivity_denominator",
                },
                "candidateHardGates": {
                    "schema_invalid": 0,
                    "invalid_evidence": 0,
                    "missing_output": 0,
                },
                "controlHardGates": {
                    "schema_invalid": 0,
                    "invalid_evidence": 0,
                    "missing_output": 0,
                },
                "controlFailurePolicy": "degrade_comparison_integrity_without_relabeling_as_candidate_hard_gate_failure",
                "primaryRelationDeltaMinimum": 0.05,
                "sensitivityRelationDeltaMinimum": 0.0,
            },
        }
    )
    prereg["costAccounting"] = {
        "latencyRequired": True,
        "usageRequired": True,
        "providerPriceConfigurationRequiredBeforeExecution": False,
        "providerPriceConfigurationRequiredBeforeSelection": True,
        "pricingRevisionRationale": "Pricing is intentionally deferred from execution to selection so Stage A can collect development evidence while preserving a hard pricing gate before any candidate selection or promotion.",
    }
    prereg["sourceEvidence"]["promptArtifactDigest"] = file_digest(PROMPT_ARTIFACT)
    prereg["sourceEvidence"]["backlogDigest"] = file_digest(BACKLOG)
    prereg["stageA"]["selectionProfile"] = {
        "positiveRelationCases": 7,
        "hardNegativeOrSemanticGapCases": 5,
        "safetyAbstentionOrIsolationCases": 3,
        "additionalTemporalControlCases": 1,
    }
    prereg["stageA"]["temporalPairing"] = {
        "strategy": "interleaved_paired_runs",
        "schedule": [
            {"pairId": "pair-1", "runNumber": 1, "armOrder": ["control", "candidate"]},
            {"pairId": "pair-2", "runNumber": 2, "armOrder": ["candidate", "control"]},
            {"pairId": "pair-3", "runNumber": 3, "armOrder": ["control", "candidate"]},
        ],
        "oneAttemptPerCase": True,
        "noRetryWithinEachRun": True,
    }
    prereg["status"] = "PREREGISTERED_NOT_EXECUTED"
    return prereg


def build_registry(prereg: dict[str, Any]) -> dict[str, Any]:
    registry = copy.deepcopy(load(REGISTRY_V5))
    registry.pop("registryDigest", None)
    registry["registryVersion"] = "s12.experiment-registry.v6"
    registry["openedExperimentId"] = "s12-f-07"
    registry["pendingExperiment"] = {
        "experimentId": "s12-f-07",
        "preregistration": {
            "artifact": PREREG_V2.name,
            "digest": file_digest(PREREG_V2),
        },
        "authorization": {
            "artifact": AUTHORIZATION.name,
            "status": "PENDING_USER_AUTHORIZATION",
        },
        "executionAuthorized": False,
        "stageBAuthorized": False,
    }
    registry["experiments"].append(
        {
            "experimentId": "s12-f-07",
            "hypothesis": prereg["hypothesis"],
            "dimension": "prompt",
            "permittedSplit": "development",
            "baselineConfigurationDigest": prereg["control"]["configurationDigest"],
            "candidateConfigurationDigest": prereg["candidate"]["configurationDigest"],
            "datasetManifestDigest": prereg["fixedArtifacts"]["datasetManifestDigest"],
            "metricTarget": {
                "relationMacroF1": {"direction": "higher", "minimumDelta": 0.05},
                "entityMacroF1": {"direction": "higher", "minimumDelta": -0.01},
                "abstentionAccuracy": {"direction": "higher", "minimumDelta": -0.01},
            },
            "stoppingRule": "Stop after Stage A if the candidate hard gate fails; authorize Stage B only after primary and sensitivity denominator gates, pricing-before-selection and comparison-integrity conditions pass.",
            "changedArtifacts": ["prompt"],
            "preservedArtifacts": [
                "dataset",
                "evaluator",
                "ontology",
                "policy",
                "review-contract",
                "context",
                "tool",
            ],
            "status": "REGISTERED_PENDING_AUTHORIZATION",
            "preregistration": {
                "artifact": PREREG_V2.name,
                "digest": file_digest(PREREG_V2),
            },
            "promptArtifact": prereg["promptArtifact"],
            "denominatorContract": prereg["denominatorContract"],
            "pricingContract": prereg["pricingContract"],
        }
    )
    registry["registryDigest"] = canonical_digest(registry)
    return registry


def build_authorization(prereg: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifactVersion": "s12.s12-f-07.authorization.v1",
        "experimentId": "s12-f-07",
        "status": "PENDING_USER_AUTHORIZATION",
        "approvalSource": "pending-owner-approval",
        "scope": {
            "stage": "A",
            "caseCount": prereg["stageA"]["caseCount"],
            "independentPairedRuns": prereg["stageA"]["independentPairedRuns"],
            "oneAttemptPerCase": True,
            "noRetryWithinEachRun": True,
            "developmentOnly": True,
            "heldOutInspected": False,
            "stageBAuthorized": False,
            "validationAuthorized": False,
        },
        "preregistration": {"artifact": PREREG_V2.name, "digest": file_digest(PREREG_V2)},
        "registry": {"artifact": REGISTRY_V6.name, "digest": registry["registryDigest"]},
        "pricingContract": prereg["pricingContract"],
        "credentialIncluded": False,
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }


def build_g5(registry: dict[str, Any], prereg: dict[str, Any], authorization: dict[str, Any]) -> dict[str, Any]:
    return {
        "packetVersion": "s12.g5.packet.v6",
        "status": "G5_PREPARATION_DEVELOPMENT_OPEN_PENDING_S12_F07_AUTHORIZATION",
        "approvalStatus": "APPROVED_WITH_LIMITATIONS",
        "registryVersion": registry["registryVersion"],
        "registryDigest": registry["registryDigest"],
        "datasetVersion": prereg["fixedArtifacts"]["datasetVersion"],
        "datasetManifestDigest": prereg["fixedArtifacts"]["datasetManifestDigest"],
        "pendingExperiment": {
            "experimentId": "s12-f-07",
            "preregistrationArtifact": PREREG_V2.name,
            "preregistrationDigest": file_digest(PREREG_V2),
            "authorizationArtifact": AUTHORIZATION.name,
            "authorizationDigest": file_digest(AUTHORIZATION),
            "executionAuthorized": False,
            "stageBAuthorized": False,
        },
        "denominatorContract": prereg["denominatorContract"],
        "pricingContract": prereg["pricingContract"],
        "candidateAvailable": False,
        "candidateFreezeAuthorized": False,
        "heldOutInspected": False,
        "validationAuthorized": False,
        "optimizationAuthorized": False,
        "selection": {
            "status": "NO_SELECTION",
            "reason": "S12-f-07 execution authorization is pending; no Stage A result exists.",
            "heldOutInspected": False,
        },
        "executionBlockedReasons": [
            "user authorization artifact is pending",
            "provider credentials are not requested or stored by this package",
            "pricing is not bound and selection is therefore blocked",
        ],
        "humanEvidence": False,
        "rawSensitiveDataIncluded": False,
    }


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    prereg = build_preregistration()
    write(PREREG_V2, prereg)
    registry = build_registry(prereg)
    write(REGISTRY_V6, registry)
    # Authorization v1 is a historical pending artifact.  Preparation may bind
    # its existing digest, but must never rewrite it.
    authorization = load(AUTHORIZATION)
    g5 = build_g5(registry, prereg, authorization)
    write(G5_V6, g5)
    G5_MD_V6.write_text(
        "# Sprint 12 G5 Optimization Packet v6\n\n"
        "Status: `G5_PREPARATION_DEVELOPMENT_OPEN_PENDING_S12_F07_AUTHORIZATION`\n\n"
        "S12-f-07 is registered as a prompt-only development experiment. Its execution authorization is pending; no provider call, Stage A result or candidate selection exists. Pricing is required before selection, not before Stage A execution, and the denominator contract is fail-closed on the full 48 case-runs per arm with paired common-valid sensitivity analysis.\n\n"
        f"- Registry: `{REGISTRY_V6.name}` / `{registry['registryDigest']}`\n"
        f"- Preregistration: `{PREREG_V2.name}` / `{file_digest(PREREG_V2)}`\n"
        f"- Authorization: `{AUTHORIZATION.name}` / `{file_digest(AUTHORIZATION)}`\n"
        "- Candidate hard gates: zero schema/evidence/missing-output.\n"
        "- Control failures degrade comparison integrity but do not become candidate hard-gate failures.\n"
        "- Stage B, selection, validation, freeze and held-out remain locked.\n",
        encoding="utf-8",
    )
    print(json.dumps({"registry": REGISTRY_V6.name, "g5": G5_V6.name, "status": authorization["status"]}))


if __name__ == "__main__":
    main()
