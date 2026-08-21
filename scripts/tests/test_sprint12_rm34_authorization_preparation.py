"""RM-34 exact v8 authorization preparation contract tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

import preflight_sprint12_f12_rm34 as preflight


ROOT = Path(__file__).resolve().parents[2]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm34-authorization-preparation.v1.json"
AUTH_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v8.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm34_preparation_is_exactly_bound_and_zero_call() -> None:
    result = preflight.run_preflight()
    preparation = _json(PREPARATION)
    assert result["status"] == "F12_RM34_PREPARED_ZERO_CALL"
    assert result["runtimeBlobCount"] == 22
    assert result["providerCalls"] == 0
    assert result["nextGate"] == "S12-RM-35_OWNER_AUTHORIZATION_REVIEW"
    assert preparation["providerExecutionAuthorized"] is False
    assert preparation["newAuthorizationIssued"] is False
    assert preparation["preparedLineage"]["executionCommit"] == (
        "005a35e3be3fbff40fcdae02dfdf79145c76934b"
    )
    assert preparation["exactRuntimeBindings"]["reportSchema"]["digest"] == (
        "sha256:c65a4f039d948e6f3a59750001e58199bfc98e57e2f2f3ac838070ef5f6f6ad5"
    )
    assert preparation["integrityFindings"]["ownerReviewReconciliationRequired"] is True
    assert preparation["integrityFindings"]["providerExecutionBlockedUntilReconciled"] is True
    assert preparation["preparedLineage"]["outputPath"].endswith(
        "s12-f-12-stage-a-report.v8.json"
    )
    assert preparation["executionBounds"] == {
        "providerCalls": 144,
        "stage1ProviderCalls": 48,
        "stage2PredictedEntitiesCalls": 48,
        "stage2GoldEntitiesCalls": 48,
        "relationBranchOutputs": 96,
        "retryPolicy": "none",
        "retryAuthorized": False,
        "outputOverwrite": False,
        "outputOverwriteAuthorized": False,
        "outputPath": "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json",
        "costCeilingUsd": "10.00",
    }


def test_rm34_is_not_an_issued_authorization() -> None:
    preparation = _json(PREPARATION)
    schema = _json(AUTH_SCHEMA)
    Draft202012Validator.check_schema(schema)
    # The issued v8 schema intentionally requires providerExecutionAuthorized=true.
    # RM-34 must remain visibly invalid as an issued authorization until RM-35.
    assert list(Draft202012Validator(schema).iter_errors(preparation))
    assert preparation["authorizationContract"]["preparedArtifactIsNotAnIssuedAuthorization"] is True
    assert preparation["authorizationContract"]["rm25AuthorizationReused"] is False


def test_rm34_preserves_immutable_v6_accounting() -> None:
    report = _json(REPORT_V6)
    assert _digest(REPORT_V6) == (
        "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    )
    assert report["accounting"]["providerCallsAttempted"] == 144
    assert report["accounting"]["retryCount"] == 0
    assert not (ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json").exists()
