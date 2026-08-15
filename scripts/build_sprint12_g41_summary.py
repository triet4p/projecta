#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Derive the G4.1 candidate summary from the operational candidate report."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_CANDIDATE_PATH = (
    ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-development.v1.json"
)
CANDIDATE_PATH = (
    ROOT
    / "evaluation/sprint-12/optimization/contract-candidate-v2-stability/runs/run-03.report.v1.json"
    if (
        ROOT
        / "evaluation/sprint-12/optimization/contract-candidate-v2-stability/runs/run-03.report.v1.json"
    ).exists()
    else LEGACY_CANDIDATE_PATH
)
PACKET_PATH = ROOT / "evaluation/sprint-12/baseline/g4.1-contract-alignment.v1.json"
LEGACY_STABILITY_PATH = (
    ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-stability.v1.json"
)
STABILITY_PATH = (
    ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-stability.v2.json"
    if (
        ROOT / "evaluation/sprint-12/optimization/contract-candidate-v2-stability.v2.json"
    ).exists()
    else LEGACY_STABILITY_PATH
)
S73_PATH = ROOT / "evaluation/sprint-12/optimization/s12-73-prompt-supersession.v1.json"
S73_FOLLOWUP_PATH = ROOT / "evaluation/sprint-12/optimization/s12-73-prompt-followup-stability.v2.json"
S73_DIAGNOSTIC_PATH = ROOT / "evaluation/sprint-12/optimization/s12-73-targeted-diagnostics.v1.json"


def _count(failure_counts: object, name: str) -> int:
    if not isinstance(failure_counts, dict):
        raise TypeError("candidate operational failureCounts must be an object")
    value = failure_counts.get(name, 0)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"candidate failure count is invalid: {name}")
    return value


def build_summary() -> dict[str, object]:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    operational = candidate.get("operational")
    if not isinstance(operational, dict):
        raise TypeError("candidate report is missing operational accounting")
    failure_counts = operational.get("failureCounts")
    schema_invalid = _count(failure_counts, "schema_invalid")
    invalid_evidence = _count(failure_counts, "invalid_evidence")
    failures = candidate.get("failures")
    if not isinstance(failures, list):
        raise TypeError("candidate report failures must be a list")
    observed = {
        "schema_invalid": sum(
            item.get("failureClass") == "schema_invalid"
            for item in failures
            if isinstance(item, dict)
        ),
        "invalid_evidence": sum(
            item.get("failureClass") == "invalid_evidence"
            for item in failures
            if isinstance(item, dict)
        ),
    }
    if observed != {
        "schema_invalid": schema_invalid,
        "invalid_evidence": invalid_evidence,
    }:
        raise ValueError(
            "candidate failure list and operational failureCounts disagree"
        )
    summary = {
        "sourceReport": os.path.relpath(CANDIDATE_PATH, PACKET_PATH.parent).replace(
            "\\", "/"
        ),
        "caseCount": candidate.get("caseCount"),
        "failureCounts": dict(failure_counts),
        "schemaInvalidCount": schema_invalid,
        "invalidEvidenceCount": invalid_evidence,
        "derivedFromOperationalAccounting": True,
    }
    historical = packet.get("historicalContractEvidence")
    if not isinstance(historical, dict):
        historical = {}
    contract_candidate = historical.get("contractCandidate") or packet.get(
        "contractCandidate"
    )
    if not isinstance(contract_candidate, dict):
        raise TypeError("G4.1 packet is missing contractCandidate")
    contract_candidate.update(
        {
            "artifact": os.path.relpath(CANDIDATE_PATH, PACKET_PATH.parent).replace(
                "\\", "/"
            ),
            "status": candidate.get("status"),
            "caseCount": candidate.get("caseCount"),
            "missingOutputCount": candidate.get("missingOutputCount"),
            "schemaInvalidCount": schema_invalid,
            "invalidEvidenceCount": invalid_evidence,
            "relationContractRepresentable": candidate.get("hardInvariants", {}).get(
                "relationContractRepresentable", False
            ),
            "validationAuthorized": candidate.get("validationAuthorized", False),
        }
    )
    if STABILITY_PATH.exists():
        stability = json.loads(STABILITY_PATH.read_text(encoding="utf-8"))
        stability_counts = stability.get("aggregateFailureCounts")
        if not isinstance(stability_counts, dict):
            raise TypeError("stability aggregateFailureCounts must be an object")
        stability_gate = {
            "artifact": os.path.relpath(STABILITY_PATH, PACKET_PATH.parent).replace(
                "\\", "/"
            ),
            "status": stability.get("status"),
            "independentRunCount": stability.get("independentRunCount"),
            "totalCaseExecutions": stability.get("totalCaseExecutions"),
            "fixedModelConfiguration": stability.get("fixedModelConfiguration"),
            "noRetryWithinEachRun": stability.get("noRetryWithinEachRun"),
            "aggregateFailureCounts": dict(stability_counts),
            "derivedFromArtifact": True,
        }
        if stability.get("status") == "STABILITY_GATE_FAIL" and CANDIDATE_PATH != LEGACY_CANDIDATE_PATH:
            packet["status"] = "CONTRACT_ALIGNED_STABILITY_FAILED"
            packet["decisionBoundary"] = {
                **packet.get("decisionBoundary", {}),
                "promptExperimentsAuthorized": True,
                "validationAuthorized": False,
                "custodyAuthorized": False,
                "baselineOverwriteAllowed": False,
                "nextAction": "run S12-73 prompt-only supersession experiment on 8 development cases x 3 runs",
            }
    if CANDIDATE_PATH != LEGACY_CANDIDATE_PATH:
        packet["supersessionReview"] = {
            "artifact": "supersession-review.v2.json",
            "adjudicationArtifact": "supersession-adjudication.v2.json",
            "status": "ADJUDICATED_DATASET_AMENDMENT_PUBLISHED",
            "goldChanged": True,
            "goldChangedSilently": False,
            "ontologyChangeRequired": False,
            "candidateContractGap": True,
        }
    if S73_PATH.exists():
        prompt_experiment = json.loads(S73_PATH.read_text(encoding="utf-8"))
        prompt_evidence = {
            "artifact": os.path.relpath(S73_PATH, PACKET_PATH.parent).replace(
                "\\", "/"
            ),
            "status": prompt_experiment.get("status"),
            "candidateSchemaEvidenceClean": prompt_experiment.get(
                "candidateSchemaEvidenceClean"
            ),
            "semanticMetricsImproved": prompt_experiment.get("semanticMetricsImproved"),
            "linkMetricUsable": prompt_experiment.get("linkMetricUsable"),
            "nextAction": prompt_experiment.get("nextAction"),
        }
        if S73_FOLLOWUP_PATH.exists():
            followup = json.loads(S73_FOLLOWUP_PATH.read_text(encoding="utf-8"))
            prompt_evidence["followupArtifact"] = os.path.relpath(
                S73_FOLLOWUP_PATH, PACKET_PATH.parent
            ).replace("\\", "/")
            prompt_evidence["followupStatus"] = followup.get("status")
            prompt_evidence["followupFailureCounts"] = followup.get(
                "aggregateFailureCounts"
            )
            prompt_evidence["nextAction"] = (
                "do not promote S12-73 candidate; revise prompt/contract diagnosis and keep validation, freeze and held-out locked"
                if followup.get("status") == "STABILITY_GATE_FAIL"
                else prompt_experiment.get("nextAction")
            )
            packet["decisionBoundary"]["nextAction"] = (
                "do not promote S12-73 candidate; revise prompt/contract diagnosis and keep validation, freeze and held-out locked"
                if followup.get("status") == "STABILITY_GATE_FAIL"
                else prompt_experiment.get("nextAction")
            )
        if S73_DIAGNOSTIC_PATH.exists():
            diagnostic = json.loads(S73_DIAGNOSTIC_PATH.read_text(encoding="utf-8"))
            prompt_evidence["targetedDiagnosticArtifact"] = os.path.relpath(
                S73_DIAGNOSTIC_PATH, PACKET_PATH.parent
            ).replace("\\", "/")
            prompt_evidence["targetedDiagnosticStatus"] = diagnostic.get("status")
            prompt_evidence["targetedDiagnosticCaseIds"] = diagnostic.get("caseIds")
            prompt_evidence["targetedDiagnosticFailureCounts"] = diagnostic.get(
                "failureCounts"
            )
        prompt_evidence["evidenceScope"] = "currentPromptExperimentEvidence"
        packet["currentPromptExperimentEvidence"] = prompt_evidence
    historical.update(
        {
            "evidenceScope": "historicalContractEvidence",
            "contractCandidate": contract_candidate,
            "summary": summary,
        }
    )
    if STABILITY_PATH.exists():
        historical["stabilityGate"] = stability_gate
    packet["historicalContractEvidence"] = historical
    packet.pop("contractCandidate", None)
    packet.pop("summary", None)
    packet.pop("stabilityGate", None)
    packet.pop("promptExperiment", None)
    packet["evidenceBoundaryVersion"] = "s12.g4.1.evidence-boundary.v2"
    return packet


def main() -> None:
    packet = build_summary()
    PACKET_PATH.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": packet["status"],
                "schemaInvalidCount": packet["historicalContractEvidence"]["summary"]["schemaInvalidCount"],
                "invalidEvidenceCount": packet["historicalContractEvidence"]["summary"]["invalidEvidenceCount"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
