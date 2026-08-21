from __future__ import annotations

import hashlib
import json
from pathlib import Path

import preflight_sprint12_f12_rm45 as preflight
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"
AUTHORIZATION = OPT / "s12-f-12-rm45-authorization.v9.json"
OWNER_REVIEW = OPT / "s12-f-12-rm45-owner-review.v1.json"
TRANSITION = OPT / "s12-f-12-rm45-authorization-transition.v1.json"
AUTHORIZATION_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json"
PACKET = OPT / "g5-packet.v31.rm45-authorization.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm45_preflight_is_zero_call_and_single_use_bounded() -> None:
    result = preflight.run_preflight()
    assert result["status"] == "F12_RM45_AUTHORIZED_ZERO_CALL_PRECHECK"
    assert result["executionCommitSha"] == "f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e"
    assert result["authorizedExecutions"] == 1
    assert result["authorizedProviderCalls"] == 144
    assert result["providerCallsPerformed"] == 0
    assert result["runtimeBlobCount"] == 19
    assert result["relationBranchOutputs"] == 96
    assert result["retryCount"] == 0
    assert result["costCeilingUsd"] == "10.00"
    assert result["outputExists"] is False


def test_rm45_authorization_schema_and_owner_transition_are_digest_bound() -> None:
    authorization = _json(AUTHORIZATION)
    schema = _json(AUTHORIZATION_SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(authorization)) == []

    owner_review = _json(OWNER_REVIEW)
    transition = _json(TRANSITION)
    assert owner_review["issuedAuthorization"]["digest"] == _digest(AUTHORIZATION)
    assert transition["ownerReview"]["digest"] == _digest(OWNER_REVIEW)
    assert transition["authorization"]["digest"] == _digest(AUTHORIZATION)
    assert transition["preparation"]["digest"] == _digest(
        OPT / "s12-f-12-rm44-authorization-preparation.v1.json"
    )
    assert _digest(PACKET) == _json(ROOT / "evaluation/sprint-12/current-state.v1.json")["currentEvidence"]["g5Packet"]["digest"]


def test_rm45_authorization_keeps_all_downstream_locks_closed() -> None:
    authorization = _json(AUTHORIZATION)
    transition = _json(TRANSITION)
    packet = _json(PACKET)

    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["providerCalls"] == 144
    assert authorization["retryPolicy"] == "none"
    assert authorization["costCeilingUsd"] == "10.00"
    assert authorization["outputPath"].endswith("s12-f-12-stage-a-report.v9.json")
    for artifact in (transition["currentDecisionState"], packet["authorizationBoundary"]):
        for key in (
            "retryAuthorized",
            "outputOverwriteAuthorized",
            "validationAccessAuthorized",
            "heldOutAccessAuthorized",
            "stageBAuthorized",
            "candidateSelectionAuthorized",
            "promotionAuthorized",
        ):
            assert artifact[key] is False
    for key in (
        "heldOutAccessAuthorized",
        "validationAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert authorization[key] is False
    assert transition["currentDecisionState"]["authorizedExecutions"] == 1
    assert transition["currentDecisionState"]["providerCallsPerformed"] == 0
    assert packet["currentLineage"]["authorizationSpent"] is False
    assert packet["currentLineage"]["stageAReportExists"] is False
