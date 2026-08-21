"""Contract tests for the bounded G3.1-B pilot approval packet."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "evaluation/sprint-12/gates/g3.1-b-pilot-approval.v1.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_g31_b_approval_is_scoped_and_does_not_authorize_provider_or_heldout() -> None:
    packet = read_json(PACKET)
    assert packet["reportVersion"] == "s12.g31-b-pilot-approval.v1"
    assert packet["status"] == "G3_1_B_PILOT_APPROVED_WITH_SCOPE_LIMITS"
    assert packet["decision"] == {
        "scaleUp": "approved-for-passed-v3-patterns-only",
        "providerExecutionAuthorized": False,
        "heldOutAccessAuthorized": False,
        "g5ExperimentAuthorized": False,
        "nextAction": "S12-R14 may scale approved v3 patterns; retain all G5 and test-custody blocks.",
    }
    assert packet["humanEvidence"] is False
    assert packet["qualifiedHumanEvidence"] is False
    assert packet["rawSensitiveDataIncluded"] is False
    assert "rawText" not in json.dumps(packet, ensure_ascii=False)


def test_g31_b_approval_reviews_representatives_timelines_and_metric_computability() -> None:
    packet = read_json(PACKET)
    representatives = packet["representativeCaseReview"]
    assert len(representatives) == 12
    assert len({row["caseId"] for row in representatives}) == 12
    assert any("ABSTENTION.EXPLICIT_UNCERTAINTY" in row["reviewedRuleIds"] for row in representatives)
    assert len(packet["longitudinalTimelineReview"]) == 6
    assert all(row["eventCount"] == 8 for row in packet["longitudinalTimelineReview"])
    assert all(row["checkpointSequences"] == [2, 4, 6, 8] for row in packet["longitudinalTimelineReview"])
    assert all(row["contradictionCheckpointCount"] == 2 for row in packet["longitudinalTimelineReview"])
    assert packet["normalizedTemplateReview"]["pass"] is True
    metric = packet["metricComputability"]
    assert metric["missingReportFields"] == []
    assert metric["relationSemanticIdentityBound"] is True
    assert metric["relationEvidenceSupportBound"] is True
    assert metric["relationEvidenceExactBound"] is True
    assert metric["perCaseDenominatorsRequired"] is True
    assert metric["perSliceDenominatorsRequired"] is True
    assert metric["pooledOnlySummaryForbidden"] is True


def test_g31_b_approval_keeps_pilot_gaps_explicit() -> None:
    gaps = read_json(PACKET)["coverageReview"]["pilotGapsForScale"]
    assert gaps["entityTypesWithoutPositiveCases"] == ["Assumption", "ResearchFinding"]
    assert gaps["predicatesWithoutPositiveCases"] == ["resolves"]
    assert gaps["journeysNotInPilot"] == ["J7", "J8"]
