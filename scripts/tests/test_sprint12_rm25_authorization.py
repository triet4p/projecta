from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import run_sprint12_f12_stage_a_v6 as runner

ROOT = Path(__file__).resolve().parents[2]
OPT = ROOT / "evaluation/sprint-12/optimization"
AUTHORIZATION = OPT / "s12-f-12-rm25-authorization.v1.json"
PREPARATION = OPT / "s12-f-12-rm24-preparation.v1.json"
REVIEW = OPT / "s12-f-12-rm25-owner-review.v1.json"
TRANSITION = OPT / "s12-f-12-rm25-authorization-transition.v1.json"
OUTPUT = OPT / "s12-f-12-stage-a-report.v6.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm25_authorization_is_schema_valid_and_runner_accepted() -> None:
    authorization = runner.validate_authorization(AUTHORIZATION)
    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["providerCalls"] == 144
    assert authorization["retryPolicy"] == "none"
    assert authorization["commitSha"] == "e047911e2e2d513f2b8751965dd702b2c1fe9d5a"
    assert OUTPUT.exists() is False


def test_rm25_owner_review_and_transition_bind_exact_artifacts() -> None:
    review = _json(REVIEW)
    transition = _json(TRANSITION)
    assert review["reviewedPreparation"]["digest"] == _digest(PREPARATION)
    assert review["issuedAuthorization"]["digest"] == _digest(AUTHORIZATION)
    assert transition["ownerReview"]["digest"] == _digest(REVIEW)
    assert transition["authorization"]["digest"] == _digest(AUTHORIZATION)
    assert transition["currentDecisionState"]["providerCallsPerformed"] == 0
    assert transition["currentDecisionState"]["authorizedExecutions"] == 1


def test_rm25_keeps_every_broader_governance_gate_closed() -> None:
    authorization = _json(AUTHORIZATION)
    for key in (
        "heldOutInspected",
        "heldOutAccessAuthorized",
        "validationAccessAuthorized",
        "stageBAuthorized",
        "candidateSelectionAuthorized",
        "promotionAuthorized",
    ):
        assert authorization[key] is False


def test_rm25_rejects_tampered_authorization(tmp_path: Path) -> None:
    authorization = _json(AUTHORIZATION)
    authorization["providerCalls"] = 145
    tampered = tmp_path / "authorization.json"
    tampered.write_text(json.dumps(authorization), encoding="utf-8")
    with pytest.raises(Exception, match="authorization schema validation failed"):
        runner.validate_authorization(tampered)
