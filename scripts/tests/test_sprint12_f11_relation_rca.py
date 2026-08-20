"""Offline RCA tests for the completed S12-f-11 execution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_sprint12_f11_relation_rca import analyze


def test_rca_recomputes_gold_profile_and_oracle_ceiling() -> None:
    result = analyze()
    assert result["frozenProfile"]["caseCount"] == 16
    assert result["frozenProfile"]["caseRuns"] == 48
    assert result["frozenProfile"]["goldRelationsPerRun"] == 8
    assert result["frozenProfile"]["goldRelationInstancesAcrossRuns"] == 24
    ceiling = result["oracleRelationCeiling"]
    assert ceiling["goldEntityEndpointResolution"]["rate"] == 1.0
    assert ceiling["goldEvidenceSpanValidity"]["rate"] == 1.0
    assert ceiling["perfectTwoStepRelationSemanticMicroF1"] == 1.0


def test_rca_preserves_sanitized_report_limitations_and_governance() -> None:
    result = analyze()
    assert result["observedExecutionSignals"]["providerCalls"] == 48
    assert result["observedExecutionSignals"]["branchOutputs"] == 96
    assert (
        result["observedExecutionSignals"]["candidateMaterializerEvidenceFailures"]
        == 53
    )
    assert result["errorDecomposition"]["exactBucketDecompositionAvailable"] is False
    assert result["architectureAssessment"]["preregistrationNow"] is False
    assert result["governance"]["f11RerunAuthorized"] is False
    assert result["rawSensitiveDataIncluded"] is False
