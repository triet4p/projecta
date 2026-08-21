from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"
sys.path.insert(0, str(ROOT / "scripts"))

import preflight_sprint12_f12_rm32 as preflight


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


PACKAGE = OPT / "s12-f-12-rm32-execution-package.v8.json"
PREREG = OPT / "s12-f-12-rm32-preregistration.v8.json"
FREEZE = OPT / "s12-f-12-rm32-technical-freeze.v8.json"
REPORT_V6 = OPT / "s12-f-12-stage-a-report.v6.json"


def test_rm32_preflight_is_zero_call_and_does_not_touch_historical_report() -> None:
    before = _digest(REPORT_V6)
    expected_commit = _json(PACKAGE)["executionCommitSha"]
    result = preflight.run_preflight()
    assert result == {
        "status": "F12_RM32_READY_ZERO_CALL",
        "preparationScope": "S12-RM-32",
        "lineageVersion": "v8",
        "executionCommitSha": expected_commit,
        "runtimeBlobCount": 22,
        "preparationEvidenceCount": 4,
        "providerCalls": 0,
        "retryCount": 0,
        "historicalReportDigest": before,
        "outputPath": "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json",
    }
    assert _digest(REPORT_V6) == "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"


def test_rm32_lineage_binds_rm31_rm30_and_exact_commit() -> None:
    package = _json(PACKAGE)
    prereg = _json(PREREG)
    freeze = _json(FREEZE)
    assert package["executionCommitSha"] == "79447940f90b17dd22bfa2042be4c9ef2f8c54d1"
    assert prereg["executionCommitSha"] == package["executionCommitSha"]
    assert freeze["executionCommitSha"] == package["executionCommitSha"]
    assert package["rm31ApprovalTransition"]["digest"] == _digest(
        OPT / "s12-f-12-rm31-approval-transition.v1.json"
    )
    assert package["rm30Diagnostic"]["reportDigest"] == _digest(
        OPT / "s12-f-12-rm30-offline-diagnostic-report.v1.json"
    )
    assert package["rm30Diagnostic"]["schemaDigest"] == _digest(
        EVAL / "harness/s12-f-12-offline-diagnostic-report.schema.v1.json"
    )
    assert freeze["executionPackageDigest"] == _digest(PACKAGE)
    assert freeze["preregistrationDigest"] == _digest(PREREG)
    assert package["exactCommitValidated"] is True
    assert package["runtimeBinding"]["digestMode"] == "git_blob_sha256"
    assert set(package["runtimeBoundDigests"]).isdisjoint(package["preparationEvidence"])
    assert package["runtimeBoundDigests"]["evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"] == preflight.git_blob_digest(
        package["executionCommitSha"],
        "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json",
    )


def test_rm32_governance_is_preparation_only() -> None:
    package = _json(PACKAGE)
    prereg = _json(PREREG)
    freeze = _json(FREEZE)
    for artifact in (package, prereg, freeze):
        assert artifact["preparationScope"] == "S12-RM-32"
        assert artifact["lineageVersion"] == "v8"
        assert artifact["preregistrationIssued"] is False
        assert artifact["technicalFreezeIssued"] is False
        assert artifact["providerExecutionAuthorized"] is False
        assert artifact["newAuthorizationIssued"] is False
        assert artifact["validationAccessAuthorized"] is False
        assert artifact["heldOutAccessAuthorized"] is False
        assert artifact["stageBAuthorized"] is False
        assert artifact["candidateSelectionAuthorized"] is False
        assert artifact["promotionAuthorized"] is False
    governance = package["governance"]
    assert governance["supersedingLineagePreparationAuthorized"] is True
    assert governance["preregistrationPreparationAuthorized"] is True
    assert governance["technicalFreezePreparationAuthorized"] is True
    assert governance["executionPackagePreparationAuthorized"] is True
    assert package["plannedProviderCalls"] == 144
    assert package["providerCallsPerformed"] == 0
    assert package["retryCount"] == 0


def test_rm32_preflight_is_provider_neutral() -> None:
    source = (ROOT / "scripts/preflight_sprint12_f12_rm32.py").read_text(encoding="utf-8")
    assert "provider_adapter" not in source
    assert "run_sprint12_f12_stage_a" not in source
    assert "OUTPUT.exists()" in source
