"""Focused custody and policy checks for S12-RM-54."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
OPT = EVAL / "optimization"
HARNESS = EVAL / "harness"
V1 = ROOT / "docs/sprint-plans/sprint-12/human-first-extraction-framework.v1.md"
V2 = ROOT / "docs/sprint-plans/sprint-12/human-first-extraction-framework.v2.md"
REVIEW = OPT / "s12-f-12-rm54-design-review.v1.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _git_blob_digest(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return f"sha256:{hashlib.sha256(result.stdout).hexdigest()}"


def test_rm54_design_review_validates_and_binds_both_framework_versions() -> None:
    review = _json(REVIEW)
    validate(review, _json(HARNESS / "s12-f-12-rm54-design-review.schema.v1.json"))
    assert review["sourceDesign"]["digest"] == _digest(V1)
    assert review["sourceDesign"]["digest"] == _git_blob_digest(
        "docs/sprint-plans/sprint-12/human-first-extraction-framework.v1.md"
    )
    assert review["revisedDesign"]["digest"] == _digest(V2)
    assert review["verification"]["sourceDesignUnchanged"] is True
    assert review["verification"]["providerCalls"] == 0
    assert review["verification"]["humanBusinessEvidencePresent"] is False


def test_rm54_resolves_policy_categories_and_keeps_authority_closed() -> None:
    review = _json(REVIEW)
    disposition = review["disposition"]
    verification = review["verification"]
    assert len(review["resolvedPolicyCategories"]) >= 10
    assert len(review["ownerGatedDeferrals"]) >= 2
    assert len(review["nonGoals"]) >= 8
    assert verification["policyCategoriesResolved"] is True
    assert verification["failClosedDefaultsRecorded"] is True
    assert verification["ownerGatedDeferralsRecorded"] is True
    assert verification["noOntologyArtifacts"] is True
    for key in (
        "implementationAuthorized",
        "providerExecutionAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
        "ontologyProductionChangeAuthorized",
        "humanBusinessQualityClaim",
    ):
        assert disposition[key] is False
    assert review["nextPermittedAction"] == (
        "S12-RM-55_DEFINE_IMMUTABLE_SOURCEVERSION_AND_SOURCE_RECEIPT_CONTRACT"
    )


def test_rm54_current_state_and_documents_open_rm55_only() -> None:
    current = _json(EVAL / "current-state.v1.json")
    assert current["status"] == "F_RF_POC_BASELINE_ACCEPTED_DENSE_HARD_V4_FAILED_STRATEGY_REDESIGN_REQUIRED"
    assert current["nextTasks"] == [
        "DENSE_HARD_V4_STRATEGY_REDESIGN_REQUIRES_NEW_AUTHORITY",
    ]
    assert current["currentEvidence"]["rm54DesignReview"]["digest"] == _digest(REVIEW)
    assert current["experimentState"]["currentGovernance"]["humanFirstDesignAccepted"] is True
    assert current["experimentState"]["currentGovernance"][
        "sourceVersionContractDefinitionAuthorized"
    ] is False
    assert current["experimentState"]["currentGovernance"][
        "sourceVersionContractAccepted"
    ] is True
    assert current["experimentState"]["currentGovernance"]["textAnchorContractAccepted"] is True
    assert current["experimentState"]["currentGovernance"]["perItemValidationDefinitionAuthorized"] is False
    assert current["experimentState"]["currentGovernance"]["perItemValidationAccepted"] is True
    assert current["experimentState"]["currentGovernance"]["relationGateDefinitionAuthorized"] is False
    assert current["experimentState"]["currentGovernance"]["relationGateAccepted"] is True
    assert current["experimentState"]["currentGovernance"]["evidenceSelectionDefinitionAuthorized"] is False
    assert current["experimentState"]["currentGovernance"]["evidenceSelectionAccepted"] is True
    assert current["experimentState"]["currentGovernance"]["constrainedRelationDefinitionAuthorized"] is False
    assert current["experimentState"]["currentGovernance"]["constrainedRelationAccepted"] is True
    assert current["experimentState"]["currentGovernance"][
        "textAnchorContractDefinitionAuthorized"
    ] is False
    assert current["experimentState"]["currentGovernance"][
        "humanFirstDesignReviewAuthorized"
    ] is False

    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    assert "[x] **S12-RM-54" in plan
    assert "[x] **S12-RM-55" in plan
    assert "[x] **S12-RM-56" in plan
    assert "human-first-extraction-framework.v2.md" in plan
