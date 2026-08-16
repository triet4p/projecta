"""Artifact-level guard tests for S12-f-10 Approval B."""

# ruff: noqa: I001

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from run_sprint12_next_tool_experiment import (
    FINAL_PACKAGE,
    validate_final_execution_package,
    validate_stage_a_authorization,
)


OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
AUTHORIZATION = OPTIMIZATION / "s12-f-10-approval-b.v1.json"
OUTPUT = OPTIMIZATION / "s12-f-10-stage-a-report.v5.json"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_approval_b_is_exactly_bounded_and_validates_without_execution() -> None:
    authorization = _read(AUTHORIZATION)
    assert authorization["status"] == "APPROVED_FOR_DEVELOPMENT_STAGE_A"
    assert authorization["providerExecutionAuthorized"] is True
    assert authorization["providerCallsPerformedAtIssuance"] is False
    assert authorization["stageAExecutedAtIssuance"] is False
    assert authorization["providerCalls"] == 48
    assert authorization["branchOutputs"] == 96
    assert authorization["retryPolicy"] == "none"
    assert authorization["heldOutAccessAuthorized"] is False
    assert authorization["stageBAuthorized"] is False
    assert authorization["candidateSelectionAuthorized"] is False
    assert not OUTPUT.exists()

    package = validate_final_execution_package(FINAL_PACKAGE, output_path=OUTPUT)
    validated = validate_stage_a_authorization(
        package,
        package_path=FINAL_PACKAGE,
        authorization_path=AUTHORIZATION,
        output_path=OUTPUT,
        adapter_digest=authorization["providerAdapter"]["digest"],
        runtime_configuration_digest=authorization["runtimeConfiguration"][
            "digest"
        ],
        require_concrete_provider_binding=True,
    )
    assert validated == authorization


def test_approval_b_binds_approval_a_and_freeze_without_mutating_history() -> None:
    authorization = _read(AUTHORIZATION)
    approval_a = _read(ROOT / authorization["approvalA"]["path"])
    freeze = _read(ROOT / authorization["freezeRecord"]["path"])
    package = _read(ROOT / authorization["executionPackage"]["path"])

    assert approval_a["status"] == "APPROVED_FOR_ISSUANCE_ONLY"
    assert approval_a["providerExecutionAuthorized"] is False
    assert freeze["providerExecutionAuthorized"] is False
    assert package["providerExecutionAuthorized"] is False
    assert authorization["commitSha"] == approval_a["commitSha"] == freeze["commitSha"]
