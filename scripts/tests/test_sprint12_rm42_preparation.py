from __future__ import annotations

import hashlib
import json
from pathlib import Path

import preflight_sprint12_f12_rm42 as preflight

ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"
PACKAGE = OPT / "s12-f-12-rm42-execution-package.v9.json"
PREREG = OPT / "s12-f-12-rm42-preregistration.v9.json"
FREEZE = OPT / "s12-f-12-rm42-technical-freeze.v9.json"
REPORT_V6 = OPT / "s12-f-12-stage-a-report.v6.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm42_preflight_is_zero_call_and_preserves_historical_report() -> None:
    result = preflight.run_preflight()
    assert result["status"] == "F12_RM42_READY_ZERO_CALL"
    assert result["lineageVersion"] == "v9"
    assert result["providerCalls"] == 0
    assert result["retryCount"] == 0
    assert result["plannedProviderCalls"] == 144
    assert result["plannedRelationBranchOutputs"] == 96
    assert result["historicalReportDigest"] == _digest(REPORT_V6)
    assert not (OPT / "s12-f-12-stage-a-report.v8.json").exists()
    assert not (OPT / "s12-f-12-stage-a-report.v9.json").exists()


def test_rm42_binds_rm41_rm40_and_exact_commit_blob_custody() -> None:
    package = _json(PACKAGE)
    prereg = _json(PREREG)
    freeze = _json(FREEZE)
    rm41 = OPT / "s12-f-12-rm41-approval-transition.v1.json"
    rm40 = OPT / "s12-f-12-rm40-offline-runtime-package.v1.json"
    assert package["executionCommitSha"] == prereg["executionCommitSha"] == freeze["executionCommitSha"]
    assert package["rm41ApprovalTransition"]["digest"] == _digest(
        OPT / "s12-f-12-rm41-approval-transition.v1.json"
    )
    assert package["rm41OwnerReview"]["digest"] == _digest(
        OPT / "s12-f-12-rm41-owner-review.v1.json"
    )
    assert package["rm40Package"]["digest"] == _digest(rm40)
    assert package["runtimeBinding"]["digestMode"] == "git_blob_sha256"
    assert package["runtimeBinding"]["preparationEvidenceExcludedFromExecutionCommit"] is True
    assert set(package["runtimeBoundDigests"]).isdisjoint(package["preparationEvidence"])
    assert "s12-f-12-rm42-execution-package.v9.json" not in package["runtimeBoundDigests"]
    assert "s12-f-12-rm42-preregistration.v9.json" not in package["runtimeBoundDigests"]
    assert "s12-f-12-rm42-technical-freeze.v9.json" not in package["runtimeBoundDigests"]
    assert package["executionRunner"]["path"] == "scripts/run_sprint12_f12_stage_a_v9.py"
    assert package["executionRunner"]["providerExecutionAuthorized"] is False


def test_rm42_governance_is_preparation_only() -> None:
    package = _json(PACKAGE)
    prereg = _json(PREREG)
    freeze = _json(FREEZE)
    for artifact in (package, prereg, freeze):
        for key in (
            "preregistrationIssued",
            "technicalFreezeIssued",
            "providerExecutionAuthorized",
            "newAuthorizationIssued",
            "rerunAuthorized",
            "retryAuthorized",
            "validationAccessAuthorized",
            "heldOutAccessAuthorized",
            "stageBAuthorized",
            "candidateSelectionAuthorized",
            "promotionAuthorized",
        ):
            assert artifact[key] is False
    governance = package["governance"]
    assert governance["supersedingLineagePreparationAuthorized"] is True
    assert governance["preregistrationPreparationAuthorized"] is True
    assert governance["technicalFreezePreparationAuthorized"] is True
    assert governance["executionPackagePreparationAuthorized"] is True
    assert package["providerCallsPerformed"] == 0
    assert package["retryCount"] == 0


def test_rm42_preflight_is_provider_neutral_and_output_is_closed() -> None:
    source = (ROOT / "scripts/preflight_sprint12_f12_rm42.py").read_text(encoding="utf-8")
    assert "provider_adapter" not in source
    assert "F12ProviderAdapter" not in source
    assert "REPORT_V9.exists()" in source
    assert _json(FREEZE)["output"]["path"].endswith("s12-f-12-stage-a-report.v9.json")
