"""RM-34 exact v8 authorization preparation contract tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
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
    preparation = _json(PREPARATION)
    package = _json(ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json")
    assert preflight.require_exact_runtime_bindings(preparation, package) == 22
    # RM-34 is an immutable historical preparation; RM-35 has since advanced
    # the mutable current-state index to authorized-pending-execution.
    assert preparation["status"] == "PREPARED_PENDING_RM35_OWNER_AUTHORIZATION"
    assert preparation["providerExecutionAuthorized"] is False
    assert preparation["newAuthorizationIssued"] is False
    assert preparation["preparedLineage"]["executionCommit"] == (
        "005a35e3be3fbff40fcdae02dfdf79145c76934b"
    )
    assert preparation["exactRuntimeBindings"]["reportSchema"]["digest"] == (
        "sha256:c65a4f039d948e6f3a59750001e58199bfc98e57e2f2f3ac838070ef5f6f6ad5"
    )
    assert preparation["exactRuntimeBindings"]["preflight"]["digest"] == (
        "sha256:492cc4c9815c168233039c096d5f7bc6121773a2b7f6f84443ed587fea1f8d3e"
    )
    assert preparation["preparationEvidence"]["digestMode"] == "working_tree_sha256"
    assert preparation["preparationEvidence"]["rm34Preflight"]["path"] == (
        "scripts/preflight_sprint12_f12_rm34.py"
    )
    assert preparation["integrityFindings"]["ownerReviewReconciliationRequired"] is False
    assert preparation["integrityFindings"]["ownerReviewReconciled"] is True
    assert preparation["integrityFindings"]["providerExecutionBlockedUntilReconciled"] is False
    assert preparation["rm33CustodyErratum"]["digest"] == (
        "sha256:c72867583a722c928db1a76ebb633afdaedad73abb762397b45ca3db8a782296"
    )
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


def test_rm34_rejects_the_previous_rm32_preflight_digest_typo(tmp_path: Path) -> None:
    preparation = _json(PREPARATION)
    preparation["exactRuntimeBindings"]["preflight"]["digest"] = (
        "sha256:492cc4c9815c168233039c096d5f7bc6121773a2b6f7f84443ed587fea1f8d3e"
    )
    path = tmp_path / "preparation-typo.json"
    path.write_text(json.dumps(preparation), encoding="utf-8")
    package = _json(ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm32-execution-package.v8.json")

    with pytest.raises(ValueError, match="RM-32 preflight exact runtime binding mismatch"):
        preflight.require_exact_runtime_bindings(preparation, package)


def test_rm34_rejects_one_character_tamper_of_its_own_preflight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tampered = tmp_path / "preflight-tampered.py"
    tampered.write_bytes((ROOT / "scripts/preflight_sprint12_f12_rm34.py").read_bytes() + b"\n# tamper\n")
    monkeypatch.setattr(preflight, "RM34_PREFLIGHT", tampered)

    preparation = _json(PREPARATION)
    with pytest.raises(ValueError, match="working-tree digest mismatch"):
        preflight.require_preparation_evidence(preparation)
