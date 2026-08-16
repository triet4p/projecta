"""Mocked execution-contract tests for the next S12 tool runner."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from run_sprint12_next_tool_experiment import (
    ExecutionPackageError,
    run_authorized_stage_a,
    run_paired_schedule,
    validate_execution_package,
)
from sprint12_pricing import file_digest


def _case_ids() -> tuple[str, ...]:
    return tuple(f"dev-{index:02d}" for index in range(16))


def test_draft_package_blocks_provider_adapter_before_first_call() -> None:
    calls: list[str] = []

    def provider_call(case_id: str) -> dict[str, str]:
        calls.append(case_id)
        return {"caseId": case_id}

    try:
        validate_execution_package()
    except ExecutionPackageError as error:
        assert "not frozen" in str(error)
    else:
        raise AssertionError("draft package must remain blocked")
    assert calls == []


def test_mock_schedule_uses_one_captured_response_for_two_branches() -> None:
    calls: list[str] = []

    def provider_call(case_id: str) -> dict[str, str]:
        calls.append(case_id)
        return {"caseId": case_id, "payload": "same-response"}

    result = run_paired_schedule(
        _case_ids(),
        provider_call=provider_call,
        processors={
            "control": lambda payload: {"arm": "control", "payload": payload},
            "candidate": lambda payload: {"arm": "candidate", "payload": payload},
        },
    )

    assert result["providerCallCount"] == 48
    assert result["branchOutputCount"] == 96
    assert result["retryCount"] == 0
    assert len(calls) == 48
    assert result["trace"][0]["armOrder"] == ["control", "candidate"]
    assert result["trace"][16]["armOrder"] == ["candidate", "control"]
    assert result["trace"][32]["armOrder"] == ["control", "candidate"]
    for item in result["trace"]:
        assert item["providerCallCount"] == 1
        assert item["branchCount"] == 2
        assert len(set(item["branchInputDigests"].values())) == 1
        assert set(item["outputs"]) == {"control", "candidate"}


def test_authorized_mock_package_runs_only_after_all_guards(tmp_path: Path) -> None:
    package = json.loads(
        (
            ROOT
            / "evaluation/sprint-12/optimization/s12-next-tool-execution-package-draft.v1.json"
        ).read_text(encoding="utf-8")
    )
    package.update(
        {
            "status": "EXECUTION_PACKAGE_FROZEN",
            "providerExecutionAuthorized": True,
            "commitSha": "mock-commit",
            "executionRunnerImplemented": True,
        }
    )
    package["executionRunner"]["digest"] = "sha256:" + hashlib.sha256(
        (ROOT / "scripts/run_sprint12_next_tool_experiment.py").read_bytes()
    ).hexdigest()
    package["boundDigests"] = {
        path: file_digest(ROOT / path) for path in package["boundDigests"]
    }
    path = tmp_path / "approved-package.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    calls: list[str] = []

    result = run_authorized_stage_a(
        _case_ids(),
        provider_call=lambda case_id: calls.append(case_id) or {"caseId": case_id},
        processors={
            "control": lambda payload: payload,
            "candidate": lambda payload: payload,
        },
        package_path=path,
        commit_validator=lambda commit_sha: commit_sha == "mock-commit",
    )
    assert result["providerCallCount"] == 48
    assert len(calls) == 48
