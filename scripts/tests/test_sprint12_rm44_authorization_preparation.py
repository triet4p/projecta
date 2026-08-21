"""RM-44 exact v9 authorization-preparation contract tests."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import preflight_sprint12_f12_rm44 as preflight

ROOT = Path(__file__).resolve().parents[2]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm44-authorization-preparation.v1.json"
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm42-execution-package.v9.json"
AUTH_SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-authorization.schema.v9.json"
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_rm44_preflight_is_zero_call_and_exactly_bound() -> None:
    result = preflight.run_preflight()
    preparation = _json(PREPARATION)
    package = _json(PACKAGE)
    assert result["status"] == "F12_RM44_PREPARED_ZERO_CALL"
    assert result["runtimeBlobCount"] == 19
    assert result["providerCalls"] == 0
    assert result["plannedProviderCalls"] == 144
    assert result["plannedRelationBranches"] == 96
    assert preflight.require_exact_runtime_bindings(preparation, package) == 19
    assert preparation["preparedLineage"]["executionCommit"] == "f81103b0b8f6c19a65b8d37ccfb0d08e8aeee11e"
    assert preparation["exactRuntimeBindings"]["digestMode"] == "git_blob_sha256"
    assert preparation["preparationEvidence"]["excludedFromExactRuntimeBindings"] is True


def test_rm44_is_preparation_not_an_issued_authorization() -> None:
    preparation = _json(PREPARATION)
    schema = _json(AUTH_SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert list(Draft202012Validator(schema).iter_errors(preparation))
    assert preparation["providerExecutionAuthorized"] is False
    assert preparation["newAuthorizationIssued"] is False
    assert preparation["authorizationContract"]["preparedArtifactIsNotAnIssuedAuthorization"] is True
    assert preparation["authorizationContract"]["rm35AuthorizationReused"] is False


def test_rm44_binds_runtime_provider_model_prompt_dataset_and_bounds() -> None:
    preparation = _json(PREPARATION)
    contract = preparation["runtimeContract"]
    assert contract == {
        "providerType": "openai-response",
        "transport": "deepseek-chat-completions",
        "model": "deepseek-v4-flash",
        "promptVersion": "m3.prompt.v7-v2.two-step-extraction",
        "datasetPath": "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json",
        "retryPolicy": "none",
        "apiKeyStored": False,
        "providerPayloadStored": False,
    }
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
        "outputPath": "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json",
        "costCeilingUsd": "10.00",
    }


def test_rm44_prospective_default_path_mock_is_144_96_once_no_retry_no_overwrite() -> None:
    mock = _json(PREPARATION)["mockEvidence"]
    assert mock == {
        "mode": "prospective_default_path_deterministic_mock_only",
        "unauthorizedProviderCalls": 0,
        "authorizedProviderCalls": 144,
        "relationBranches": 96,
        "retryCount": 0,
        "outputPersistCount": 1,
        "overwriteRejected": True,
        "liveProviderCalls": 0,
        "liveRunnerInvocations": 0,
    }
    assert not (ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v8.json").exists()
    assert not (ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json").exists()


def test_rm44_preserves_v6_and_does_not_reuse_v8() -> None:
    preparation = _json(PREPARATION)
    assert _digest(REPORT_V6) == "sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233"
    assert preparation["historicalCustody"]["failedV8ReportExists"] is False
    assert preparation["historicalCustody"]["failedV8AuthorizationReused"] is False
    assert preparation["historicalCustody"]["spentRM35AuthorizationReused"] is False
    assert preparation["providerCallsPerformedAtPreparation"] == 0


def test_rm44_rejects_tampered_exact_runtime_digest() -> None:
    preparation = _json(PREPARATION)
    package = _json(PACKAGE)
    tampered = copy.deepcopy(package)
    path = next(iter(tampered["runtimeBoundDigests"]))
    tampered["runtimeBoundDigests"][path] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="exact runtime blob mismatch"):
        preflight.require_exact_runtime_bindings(preparation, tampered)


def test_rm44_rejects_one_character_tamper_of_preflight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tampered = tmp_path / "preflight-tampered.py"
    tampered.write_bytes((ROOT / "scripts/preflight_sprint12_f12_rm44.py").read_bytes() + b"\n# tamper\n")
    monkeypatch.setattr(preflight, "RM44_PREFLIGHT", tampered)
    with pytest.raises(ValueError, match="working-tree digest mismatch"):
        preflight.require_preparation_evidence(_json(PREPARATION))
