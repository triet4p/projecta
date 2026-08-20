"""Zero-call contract tests for the prepared full S12-f-11 package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f11_full_stage_a as full_stage_a
from preflight_sprint12_f11_full_stage_a import run_preflight


def test_full_package_binds_48_calls_and_96_branches() -> None:
    package = full_stage_a.validate_full_package()
    assert package["caseCount"] == 16
    assert package["providerCalls"] == 48
    assert package["branchOutputs"] == 96
    assert package["requiredSchemaValidResponses"] == 48
    assert package["expectedUsageValidResponses"] == 48
    assert package["expectedPricedCalls"] == 48
    assert package["providerExecutionAuthorized"] is False


def test_full_runtime_has_48_call_cost_proof() -> None:
    runtime = json.loads(full_stage_a.FULL_RUNTIME.read_text(encoding="utf-8"))
    assert runtime["expectedProviderCalls"] == 48
    assert runtime["expectedBranchOutputs"] == 96
    assert runtime["worstCaseCostUsd"] == "0.39105024"
    assert runtime["retryPolicy"] == "none"


def test_preflight_requires_exact_freeze_commit_and_makes_no_provider_call() -> None:
    freeze = json.loads(full_stage_a.FULL_FREEZE.read_text(encoding="utf-8"))
    freeze["commitSha"] = ""
    temporary = (
        full_stage_a.ROOT
        / "evaluation/sprint-12/optimization/.tmp-f11-freeze-test.json"
    )
    temporary.write_text(json.dumps(freeze), encoding="utf-8")
    try:
        with pytest.raises(full_stage_a.FullStageAError, match="freeze commit"):
            run_preflight(freeze_path=temporary, output_path=full_stage_a.OUTPUT)
    finally:
        temporary.unlink()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("providerCalls", 4),
        ("branchOutputs", 48),
        ("stageBAuthorized", True),
        ("candidateSelectionAuthorized", True),
    ],
)
def test_full_authorization_rejects_wrong_scope(
    field: str, value: object, tmp_path: Path
) -> None:
    authorization = {
        "status": "APPROVED_FOR_DEVELOPMENT_STAGE_A",
        "experimentId": "s12-f-11",
        "providerExecutionAuthorized": True,
        "providerCalls": 48,
        "branchOutputs": 96,
        "requiredSchemaValidResponses": 48,
        "requiredUsageValidResponses": 48,
        "expectedPricedCalls": 48,
        "retryPolicy": "none",
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
        "executionPackage": {"digest": "wrong"},
    }
    authorization[field] = value
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(authorization), encoding="utf-8")
    with pytest.raises(
        full_stage_a.FullStageAError,
        match=field if field != "providerCalls" else "providerCalls",
    ):
        full_stage_a.validate_full_authorization(
            {},
            authorization_path=path,
            package_path=full_stage_a.FULL_PACKAGE,
            output_path=tmp_path / "report.json",
            adapter_digest="adapter",
            runtime_digest="runtime",
        )
