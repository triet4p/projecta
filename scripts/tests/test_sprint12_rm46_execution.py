from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation" / "sprint-12"
OPT = EVAL / "optimization"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm46_report_is_schema_valid_and_exactly_accounted() -> None:
    report_path = OPT / "s12-f-12-stage-a-report.v9.json"
    report = _json(report_path)
    schema = _json(EVAL / "harness" / "s12-f-12-stage-a-report.schema.v9.json")
    errors = list(Draft202012Validator(schema).iter_errors(report))
    assert errors == []
    assert report["artifactVersion"] == "s12-f-12.stage-a-report.v9"
    assert report["accounting"] == {
        **report["accounting"],
        "providerCallsAttempted": 144,
        "responsesReceived": 144,
        "pricedCalls": 144,
        "usageValidResponses": 144,
        "retryCount": 0,
        "totalCostUsd": "0.00599700",
    }
    assert report["decision"]["status"] == "COMPLETED_REJECTED_HARD_GATE"
    assert report["decision"]["failedGates"] == [
        "schemaInvalid",
        "invalidEvidence",
        "thresholds",
        "sliceGates",
    ]
    assert report["metrics"]["hardGates"]["schemaInvalid"] == 5
    assert report["metrics"]["hardGates"]["invalidEvidence"] == 20
    assert report["metrics"]["hardGates"]["missingOutput"] == 0
    assert report["custody"]["rawProviderPayloadStored"] is False
    assert report["custody"]["rawSourceTextStored"] is False


def test_rm46_transition_binds_report_and_consumes_single_authorization() -> None:
    report_path = OPT / "s12-f-12-stage-a-report.v9.json"
    transition = _json(OPT / "s12-f-12-rm46-execution-transition.v1.json")
    assert transition["report"]["digest"] == _digest(report_path)
    assert transition["report"]["schemaValid"] is True
    assert transition["execution"]["invocationCount"] == 1
    assert transition["execution"]["providerCallsAttempted"] == 144
    assert transition["execution"]["relationBranchOutputs"] == 96
    assert transition["execution"]["retryCount"] == 0
    assert transition["authorization"]["spent"] is True
    assert transition["governance"]["providerExecutionAuthorized"] is False
    assert transition["governance"]["rerunAuthorized"] is False
    assert transition["governance"]["outputOverwriteAuthorized"] is False
    assert transition["governance"]["nextPermittedAction"] == (
        "S12-RM-47_OWNER_POST_RUN_DECISION"
    )


def test_rm46_preserves_v6_v8_custody_and_locks_downstream() -> None:
    report_v9 = OPT / "s12-f-12-stage-a-report.v9.json"
    v6 = OPT / "s12-f-12-stage-a-report.v6.json"
    v8 = OPT / "s12-f-12-stage-a-report.v8.json"
    transition = _json(OPT / "s12-f-12-rm46-execution-transition.v1.json")
    snapshot = _json(EVAL / "current-state-next-rm46.v1.json")
    assert _digest(v6) == "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    assert not v8.exists()
    assert transition["custody"]["supersededV8ReportExists"] is False
    assert snapshot["nonAuthoritative"] is True
    for key in (
        "retryAuthorized",
        "outputOverwriteAuthorized",
        "validationAccessAuthorized",
        "heldOutAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
        "downstreamAccessAuthorized",
    ):
        assert snapshot["governanceLocks"][key] is False
    assert snapshot["currentLineageAfterInvocation"]["reportDigest"] == _digest(report_v9)
