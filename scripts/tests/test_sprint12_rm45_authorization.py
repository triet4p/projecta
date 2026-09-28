from __future__ import annotations

import hashlib
import json
from pathlib import Path

import preflight_sprint12_f12_rm45 as preflight
import pytest
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
    with pytest.raises(ValueError, match="v8/v9|output|overwrite"):
        preflight.run_preflight()


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
    # v31 is an RM-45 historical packet; the authoritative current-state index
    # intentionally points at the later v36 RM-51 closure packet.
    assert _json(PACKET)["packetVersion"] == "s12.g5.packet.v31.rm45-authorization"


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
