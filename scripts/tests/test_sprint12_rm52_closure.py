from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"
HARNESS = EVAL / "harness"

CLOSURE = OPT / "s12-f-12-rm52-offline-closure.v1.json"
BACKLOG = OPT / "s12-f-12-rm52-error-backlog.v1.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm52_packets_validate_and_stop_at_rm53() -> None:
    closure = _json(CLOSURE)
    backlog = _json(BACKLOG)
    closure_errors = list(
        Draft202012Validator(
            _json(HARNESS / "s12-f-12-rm52-offline-closure.schema.v1.json")
        ).iter_errors(closure)
    )
    backlog_errors = list(
        Draft202012Validator(
            _json(HARNESS / "s12-f-12-rm52-error-backlog.schema.v1.json")
        ).iter_errors(backlog)
    )
    assert not closure_errors, [error.message for error in closure_errors]
    assert not backlog_errors, [error.message for error in backlog_errors]
    assert closure["nextGate"] == "S12-RM-53_OWNER_CLOSURE_REVIEW_RM52_PACKET_AND_ERROR_BACKLOG"
    assert backlog["nextGate"] == closure["nextGate"]
    assert len(backlog["items"]) >= 7


def test_rm52_binds_full_report_execution_and_authorization_custody() -> None:
    closure = _json(CLOSURE)
    custody = closure["custody"]
    assert custody["immutableReports"]["v6"]["digest"] == _digest(
        OPT / "s12-f-12-stage-a-report.v6.json"
    )
    assert custody["immutableReports"]["v9"]["digest"] == _digest(
        OPT / "s12-f-12-stage-a-report.v9.json"
    )
    failed = custody["failedV8Execution"]
    assert failed["executionFact"]["providerCallsAttempted"] == 3
    assert failed["executionFact"]["responsesReceived"] == 3
    assert failed["executionFact"]["reportPersisted"] is False
    assert failed["executionFact"]["costUsd"] is None
    assert failed["report"]["exists"] is False
    assert not (OPT / "s12-f-12-stage-a-report.v8.json").exists()
    assert {name: value["spent"] for name, value in custody["spentAuthorizations"].items()} == {
        "v7": True,
        "v8": True,
        "v9": True,
    }
    assert closure["accountingSummary"] == {
        "authorizedExecutions": 3,
        "providerCallsAttempted": 291,
        "providerResponsesReceived": 291,
        "retryCount": 0,
        "knownCostUsd": "0.01192200",
        "totalCostUsd": None,
        "costComplete": False,
        "v8CostReason": "No aggregate cost was persisted before the report-less failure.",
        "reportCount": 2,
        "reportPaths": [
            "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json",
            "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json",
        ],
        "failedV8ReportAbsent": True,
    }


def test_rm52_backlog_preserves_measured_failures_and_unknown_boundaries() -> None:
    backlog = _json(BACKLOG)
    by_id = {item["id"]: item for item in backlog["items"]}
    assert by_id["S12-F12-E01"]["measuredEvidence"]["v9"] == 5
    assert by_id["S12-F12-E02"]["measuredEvidence"]["v9"] == {
        "triggerContainmentFailure": 14,
        "endpointContainmentFailure": 6,
    }
    assert by_id["S12-F12-E03"]["category"] == "tooling_governance_lesson"
    assert by_id["S12-F12-E04"]["category"] == "unknown_causality"
    assert "raw provider payload/source" in by_id["S12-F12-E04"]["measuredEvidence"][
        "causalAttribution"
    ]
    assert by_id["S12-F12-E07"]["category"] == "external_custody_blocker"


def test_rm52_governance_is_offline_only_and_current_state_is_bound() -> None:
    closure = _json(CLOSURE)
    backlog = _json(BACKLOG)
    current = _json(EVAL / "current-state.v1.json")
    packet_path = OPT / "g5-packet.v36.rm51-closure-only.json"
    assert current["status"] == "G5_F12_PROVIDER_EXPERIMENTATION_STOPPED_OFFLINE_CLOSURE_ONLY"
    assert current["currentEvidence"]["g5Packet"]["digest"] == _digest(packet_path)
    assert closure["governance"]["providerCalls"] == 0
    assert backlog["governance"]["providerCalls"] == 0
    for artifact in (closure["governance"], backlog["governance"]):
        for key in (
            "runtimeRemediationAuthorized",
            "supersedingLineagePreparationAuthorized",
            "providerExecutionAuthorized",
            "rerunAuthorized",
            "retryAuthorized",
            "validationAccessAuthorized",
            "heldOutAccessAuthorized",
            "stageBAuthorized",
            "candidateSelectionAuthorized",
            "promotionAuthorized",
        ):
            assert artifact[key] is False, key
    assert closure["governance"]["providerExperimentationStopped"] is True

