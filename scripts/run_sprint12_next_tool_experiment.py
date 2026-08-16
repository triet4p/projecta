#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Guarded paired runner skeleton for the next S12 tool experiment.

This module deliberately has no provider dependency.  It provides the
execution guard and the provider-agnostic schedule that a future frozen
package can connect to a provider adapter.  Each case/pair captures one
response and sends independent control/candidate branches through the same
captured snapshot.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from shared_response_pairing import CapturedProviderResponse, branch_captured_response
from sprint12_pricing import file_digest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-next-tool-execution-package-draft.v1.json"
)

EXPECTED_SCHEDULE = (
    {"pairId": "pair-1", "runNumber": 1, "armOrder": ("control", "candidate")},
    {"pairId": "pair-2", "runNumber": 2, "armOrder": ("candidate", "control")},
    {"pairId": "pair-3", "runNumber": 3, "armOrder": ("control", "candidate")},
)


class ExecutionPackageError(RuntimeError):
    """Raised when a package is not safe to use for provider execution."""


def _load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def commit_is_ancestor(commit_sha: str) -> bool:
    """Return whether the authorization commit is present in the current tree."""

    if not commit_sha:
        return False
    try:
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", commit_sha, "HEAD"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def validate_execution_package(
    package_path: Path = DEFAULT_PACKAGE,
    *,
    commit_validator: Callable[[str], bool] = commit_is_ancestor,
) -> dict[str, Any]:
    """Validate authorization, commit and digest bindings before any call."""

    package = _load(package_path)
    if package.get("status") != "EXECUTION_PACKAGE_FROZEN":
        raise ExecutionPackageError("execution package is not frozen")
    if package.get("providerExecutionAuthorized") is not True:
        raise ExecutionPackageError("provider execution is not authorized")
    if package.get("heldOutInspected") is not False:
        raise ExecutionPackageError("package permits held-out inspection")
    if package.get("executionRunnerImplemented") is not True:
        raise ExecutionPackageError("execution runner is not marked implemented")

    commit_sha = str(package.get("commitSha", ""))
    if not commit_sha or not commit_validator(commit_sha):
        raise ExecutionPackageError("execution-package commit is not bound to HEAD")

    runner = package.get("executionRunner")
    if not isinstance(runner, dict):
        raise ExecutionPackageError("execution runner binding is missing")
    runner_path = str(runner.get("path", ""))
    if runner_path != "scripts/run_sprint12_next_tool_experiment.py":
        raise ExecutionPackageError("execution runner path is not allowlisted")
    if runner.get("digest") != file_digest(ROOT / runner_path):
        raise ExecutionPackageError("execution runner digest mismatch")

    mismatches = {
        path: digest
        for path, digest in package.get("boundDigests", {}).items()
        if digest != file_digest(ROOT / path)
    }
    if mismatches:
        raise ExecutionPackageError("bound execution-package digest mismatch")
    return package


def run_paired_schedule(
    case_ids: Sequence[str],
    *,
    provider_call: Callable[[str], Any],
    processors: Mapping[str, Callable[[Any], Any]],
) -> dict[str, Any]:
    """Run the deterministic three-pair schedule against one response per pair.

    The callable is an injected adapter for tests or a future authorized
    provider runner.  This function itself never imports or calls a provider.
    """

    normalized_case_ids = tuple(str(case_id) for case_id in case_ids)
    if len(normalized_case_ids) != 16 or len(set(normalized_case_ids)) != 16:
        raise ValueError("next Stage A requires exactly 16 unique development cases")
    if set(processors) != {"control", "candidate"}:
        raise ValueError("exactly control and candidate processors are required")

    trace: list[dict[str, Any]] = []
    provider_calls = 0
    for pair in EXPECTED_SCHEDULE:
        for case_id in normalized_case_ids:
            captured = CapturedProviderResponse.capture(
                f"{pair['pairId']}:{case_id}", provider_call(case_id)
            )
            provider_calls += 1
            branched = branch_captured_response(captured, {
                arm: processors[arm] for arm in pair["armOrder"]
            })
            trace.append(
                {
                    "sequence": len(trace) + 1,
                    "pairId": pair["pairId"],
                    "runNumber": pair["runNumber"],
                    "caseId": case_id,
                    "armOrder": list(pair["armOrder"]),
                    "providerCallCount": branched["providerCallCount"],
                    "branchCount": branched["branchCount"],
                    "sourceResponseDigest": branched["sourceResponseDigest"],
                    "branchInputDigests": branched["branchInputDigests"],
                    "outputs": branched["outputs"],
                }
            )
    return {
        "status": "MOCK_OR_AUTHORIZED_PAIRED_EXECUTION",
        "caseCount": len(normalized_case_ids),
        "pairCount": len(EXPECTED_SCHEDULE),
        "providerCallCount": provider_calls,
        "branchOutputCount": len(trace) * 2,
        "retryCount": 0,
        "trace": trace,
    }


def run_authorized_stage_a(
    case_ids: Sequence[str],
    *,
    provider_call: Callable[[str], Any],
    processors: Mapping[str, Callable[[Any], Any]],
    package_path: Path = DEFAULT_PACKAGE,
    commit_validator: Callable[[str], bool] = commit_is_ancestor,
) -> dict[str, Any]:
    """Validate the frozen package, then invoke the injected adapter once/case/pair."""

    validate_execution_package(package_path, commit_validator=commit_validator)
    return run_paired_schedule(
        case_ids, provider_call=provider_call, processors=processors
    )


if __name__ == "__main__":
    raise SystemExit(
        "Execution is unavailable: a frozen authorized package and provider adapter are required."
    )
