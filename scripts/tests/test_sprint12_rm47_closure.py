"""RM-47 authoritative closure consistency checks; read-only and provider-free."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm47_authoritative_packet_and_state_bind_immutable_facts() -> None:
    packet = _json(OPT / "g5-packet.v33.rm47-closure.json")
    state = _json(ROOT / "evaluation/sprint-12/current-state.v1.json")
    owner = _json(OPT / "s12-f-12-rm47-owner-decision.v1.json")
    transition = _json(OPT / "s12-f-12-rm47-decision-transition.v1.json")
    report = _json(OPT / "s12-f-12-stage-a-report.v9.json")

    assert packet["authoritative"] is True
    assert packet["ownerDecision"]["digest"] == _digest(OPT / "s12-f-12-rm47-owner-decision.v1.json")
    assert packet["decisionTransition"]["digest"] == _digest(OPT / "s12-f-12-rm47-decision-transition.v1.json")
    assert state["status"] == "G5_F12_V9_STAGE_A_CLOSED_REJECTED_NO_STAGE_B_OFFLINE_ERROR_ANALYSIS_PREPARATION_ONLY"
    assert state["currentEvidence"]["g5Packet"]["path"] == "evaluation/sprint-12/optimization/g5-packet.v33.rm47-closure.json"
    assert state["currentEvidence"]["g5Packet"]["digest"] == _digest(OPT / "g5-packet.v33.rm47-closure.json")
    assert owner["reviewedReport"]["digest"] == _digest(OPT / "s12-f-12-stage-a-report.v9.json")
    assert transition["ownerDecision"]["digest"] == _digest(OPT / "s12-f-12-rm47-owner-decision.v1.json")
    assert report["accounting"]["providerCallsAttempted"] == 144
    assert report["accounting"]["responsesReceived"] == 144
    assert report["accounting"]["retryCount"] == 0
    assert report["accounting"]["totalCostUsd"] == "0.00599700"


def test_rm47_accounting_gates_and_error_reasons_are_reconciled() -> None:
    report = _json(OPT / "s12-f-12-stage-a-report.v9.json")
    owner = _json(OPT / "s12-f-12-rm47-owner-decision.v1.json")
    accounting = report["accounting"]
    diagnostics = report["diagnostics"]
    assert owner["verifiedFacts"]["relationBranchOutputs"] == 96
    assert accounting["schemaValidResponses"] == 139
    assert accounting["failureClasses"]["schemaInvalid"] == 5
    assert diagnostics["evidenceFailureTotal"] == 20
    reasons = diagnostics["evidenceReasonCounts"]["gold-entities"]
    assert reasons["evidence_does_not_contain_trigger"] == 14
    assert reasons["evidence_does_not_contain_endpoints"] == 6
    assert report["decision"]["goldRelationsIntegrityPass"] is True
    assert report["decision"]["hardGatesPass"] is False
    assert report["decision"]["thresholdsPass"] is False
    assert report["decision"]["sliceGatesPass"] is False
    assert owner["ownerAssessment"]["qualityImprovementEstablished"] is False


def test_rm47_only_opens_offline_error_analysis() -> None:
    owner = _json(OPT / "s12-f-12-rm47-owner-decision.v1.json")
    transition = _json(OPT / "s12-f-12-rm47-decision-transition.v1.json")
    for artifact in (owner["decision"], transition["currentDecisionState"]):
        assert artifact["offlineErrorAnalysisPreparationAuthorized"] is True
        for key in (
            "offlineRemediationImplementationAuthorized",
            "supersedingLineagePreparationAuthorized",
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
    assert not (OPT / "s12-f-12-stage-a-report.v8.json").exists()
    assert _digest(OPT / "s12-f-12-stage-a-report.v6.json") == "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"


def test_rm47_report_schema_is_valid_and_immutable() -> None:
    schema = _json(ROOT / "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v9.json")
    report = _json(OPT / "s12-f-12-stage-a-report.v9.json")
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors(report))
    assert _json(OPT / "s12-f-12-rm47-owner-decision.v1.json")["reviewedReport"]["immutable"] is True
