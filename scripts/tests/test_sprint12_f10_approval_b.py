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
)


OPTIMIZATION = ROOT / "evaluation/sprint-12/optimization"
AUTHORIZATION = OPTIMIZATION / "s12-f-10-approval-b.v1.json"
OUTPUT = OPTIMIZATION / "s12-f-10-stage-a-report.v5.json"
DECISION = OPTIMIZATION / "s12-f-10-stage-a-decision.v1.json"


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_approval_b_is_exactly_bounded_and_preserved_after_execution() -> None:
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
    assert OUTPUT.is_file()

    package = validate_final_execution_package(FINAL_PACKAGE, output_path=None)
    decision = _read(DECISION)
    report = _read(OUTPUT)
    assert report["artifactVersion"] == "s12.s12-f-10.offline-stage-a-runner-report.v1"
    assert report["providerCallCount"] == 48
    assert report["branchOutputCount"] == 96
    assert package["status"] == "EXECUTION_PACKAGE_FROZEN_PENDING_AUTHORIZATION"
    assert decision["execution"]["providerCalls"] == 48
    assert decision["execution"]["branchOutputs"] == 96
    assert decision["execution"]["retryCount"] == 0
    assert decision["governance"]["stageBAuthorized"] is False
    assert decision["governance"]["candidateSelectionAuthorized"] is False
    assert decision["governance"]["nextProviderExecutionAuthorized"] is False


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
