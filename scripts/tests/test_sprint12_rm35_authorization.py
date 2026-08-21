"""RM-35 authorized v8 pre-execution custody tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

import preflight_sprint12_f12_rm35 as preflight


ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"
AUTHORIZATION = OPT / "s12-f-12-rm35-authorization.v8.json"
OWNER_REVIEW = OPT / "s12-f-12-rm35-owner-review.v1.json"
TRANSITION = OPT / "s12-f-12-rm35-authorization-transition.v1.json"
AUTHORIZATION_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json"
REPORT_V6 = OPT / "s12-f-12-stage-a-report.v6.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm35_preflight_is_authorized_but_zero_call_before_execution() -> None:
    result = preflight.run_preflight()
    assert result["status"] == "F12_RM35_AUTHORIZED_ZERO_CALL_PRECHECK"
    assert result["authorizedExecutions"] == 1
    assert result["authorizedProviderCalls"] == 144
    assert result["providerCallsPerformed"] == 0
    assert result["runtimeBlobCount"] == 22
    assert result["relationBranchOutputs"] == 96
    assert result["retryCount"] == 0
    assert result["outputExists"] is False
    assert result["nextGate"] == "S12-RM-36_EXECUTE_EXACT_V8_STAGE_A_ONCE"


def test_rm35_authorization_and_transition_are_digest_bound() -> None:
    authorization = _json(AUTHORIZATION)
    owner_review = _json(OWNER_REVIEW)
    transition = _json(TRANSITION)
    schema = _json(AUTHORIZATION_SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors(authorization))
    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["providerCalls"] == 144
    assert authorization["retryPolicy"] == "none"
    assert owner_review["issuedAuthorization"]["digest"] == _digest(AUTHORIZATION)
    assert transition["ownerReview"]["digest"] == _digest(OWNER_REVIEW)
    assert transition["authorization"]["digest"] == _digest(AUTHORIZATION)
    assert transition["currentDecisionState"]["providerExecutionAuthorized"] is True
    assert transition["currentDecisionState"]["authorizedExecutions"] == 1
    assert transition["currentDecisionState"]["providerCallsPerformed"] == 0


def test_rm35_preserves_spent_v7_and_immutable_v6_without_v8_output() -> None:
    current = _json(ROOT / "evaluation/sprint-12/current-state.v1.json")
    report_v6 = _json(REPORT_V6)
    assert current["experimentState"]["historicalLineage"]["lineageVersion"] == "v7"
    assert current["experimentState"]["historicalLineage"]["providerCallsPerformed"] == 144
    assert current["experimentState"]["currentLineage"]["lineageVersion"] == "v8"
    assert current["experimentState"]["currentLineage"]["providerCallsPerformed"] == 0
    assert _digest(REPORT_V6) == (
        "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    )
    assert report_v6["accounting"]["retryCount"] == 0
    assert not (OPT / "s12-f-12-stage-a-report.v8.json").exists()
