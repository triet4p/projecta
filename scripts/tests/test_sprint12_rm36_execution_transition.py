"""Safe post-run custody tests for the single RM-36 invocation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation/sprint-12"
OPT = EVAL / "optimization"
TRANSITION = OPT / "s12-f-12-rm36-execution-transition.v1.json"
SNAPSHOT = EVAL / "current-state-next-rm36.v1.json"
PACKET = OPT / "g5-packet.v24.rm36-execution-failure.json"
REPORT_V6 = OPT / "s12-f-12-stage-a-report.v6.json"
REPORT_V8 = OPT / "s12-f-12-stage-a-report.v8.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm36_records_one_failed_invocation_without_fabricating_a_report() -> None:
    transition = _json(TRANSITION)
    snapshot = _json(SNAPSHOT)
    packet = _json(PACKET)
    execution = transition["execution"]
    assert transition["status"].startswith("ONE_BOUNDED_V8_DEVELOPMENT_STAGE_A_EXECUTION_FAILED")
    assert transition["authorization"]["spent"] is True
    assert transition["authorization"]["reusable"] is False
    assert execution["invocationCount"] == 1
    assert execution["exitCode"] == 1
    assert execution["providerCallsAttempted"] == 3
    assert execution["providerResponsesReceived"] == 3
    assert execution["relationBranchOutputsProduced"] is None
    assert execution["costUsd"] is None
    assert execution["accountingComplete"] is False
    assert execution["reportPersisted"] is False
    assert snapshot["nonAuthoritative"] is True
    assert snapshot["currentLineageAfterInvocation"]["authorizationSpent"] is True
    assert snapshot["currentLineageAfterInvocation"]["providerCallsAttempted"] == 3
    assert packet["packetRole"] == "non-authoritative-rm36-post-run-snapshot"
    assert packet["authorizationBoundaryAfterInvocation"]["rerunAuthorized"] is False
    assert packet["authorizationBoundaryAfterInvocation"]["reportExists"] is False
    assert not REPORT_V8.exists()


def test_rm36_preserves_v6_and_defers_rm37_without_deleting_evidence() -> None:
    transition = _json(TRANSITION)
    report_v6 = _json(REPORT_V6)
    assert _digest(REPORT_V6) == (
        "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    )
    assert report_v6["accounting"]["providerCallsAttempted"] == 144
    assert report_v6["accounting"]["retryCount"] == 0
    assert transition["custody"]["historicalV6ReportDigest"] == _digest(REPORT_V6)
    assert transition["governance"]["nextPermittedAction"] == "S12-RM-37_OWNER_POST_RUN_DECISION"
    assert transition["governance"]["rerunAuthorized"] is False
