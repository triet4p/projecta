"""Contract tests for the offline f12 two-step design proposal."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = (
    ROOT
    / "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-proposal.v1.json"
)
REVIEW = (
    ROOT
    / "evaluation/sprint-12/optimization/"
    "s12-f-12-two-step-extraction-design-review.v1.json"
)


def test_design_proposal_is_review_only_and_has_oracle_arms() -> None:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    assert proposal["status"] == "DRAFT_PENDING_OWNER_REVIEW"
    assert proposal["custodyAndGovernance"]["providerExecutionAuthorized"] is False
    assert proposal["custodyAndGovernance"]["newPreregistrationIssued"] is False
    assert [arm["id"] for arm in proposal["oracleAblation"]["arms"]] == [
        "predicted-entities",
        "gold-entities",
        "gold-relations",
    ]
    assert (
        proposal["measurementContract"]["thresholdStatus"]
        == "NOT_SET_PENDING_OWNER_REVIEW"
    )
    assert proposal["oracleAblation"]["notRetroactivelyExecutable"] is True


def test_design_proposal_requires_per_case_sanitized_relation_buckets() -> None:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    required = proposal["measurementContract"]["newRequiredRecords"]
    assert "stage1EntityMetrics" in required
    assert "stage2RelationBuckets" in required
    assert "oracleAblationDenominators" in required
    assert proposal["oracleAblation"]["rawPayloadPolicy"].startswith(
        "Do not persist raw"
    )


def test_owner_review_approves_direction_but_not_preregistration() -> None:
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert review["status"] == (
        "APPROVED_WITH_REQUIRED_PREPREREGISTRATION_CONDITIONS"
    )
    assert review["architectureDecision"]["twoStepDirectionApproved"] is True
    assert review["oracleDecision"]["predictedAndGoldEntityCallsShareResponse"] is False
    assert review["requiredMeasurementContract"]["bucketModel"][
        "requireMutuallyExclusiveAxes"
    ] is True
    thresholds = review["approvedThresholds"]
    assert thresholds["hardGates"]["invalidEvidence"] == 0
    assert thresholds["stage1PredictedEntities"]["entityMacroF1Min"] == 0.85
    assert thresholds["stage2GoldEntities"]["relationSemanticMicroF1Min"] == 0.80
    assert thresholds["endToEndPredictedEntities"][
        "relationSemanticMicroF1Min"
    ] == 0.80
    assert thresholds["goldRelationsIntegrityControl"][
        "endpointResolutionRate"
    ] == 1.0
    assert review["governance"]["preregistrationAuthorized"] is False
    assert review["governance"]["providerExecutionAuthorized"] is False
    assert review["governance"]["heldOutAccessAuthorized"] is False
    assert review["governance"]["stageBAuthorized"] is False
