#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
# ]
# ///
"""Exact-commit, exact-blob, zero-call preflight for full Stage A v2."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sprint12_f11_full_stage_a_v2 as runner


def _git_blob(commit: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ("git", "show", f"{commit}:{relative_path}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout


def _blob_digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def _commit_is_exact_and_ancestor(commit: str) -> None:
    subprocess.run(
        ("git", "cat-file", "-e", f"{commit}^{{commit}}"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "merge-base", "--is-ancestor", commit, "HEAD"),
        cwd=ROOT,
        check=True,
        capture_output=True,
    )


def run_preflight(*, output_path: Path = runner.OUTPUT) -> dict[str, Any]:
    package = runner.validate_full_package(output_path=output_path)
    freeze = runner._load(runner.FULL_FREEZE)
    commit = str(freeze.get("commitSha", ""))
    if not commit:
        raise runner.FullStageAV2Error("freeze commit is empty")
    try:
        _commit_is_exact_and_ancestor(commit)
    except subprocess.CalledProcessError as error:
        raise runner.FullStageAV2Error(
            "freeze commit does not exist or is not an ancestor"
        ) from error
    if freeze.get("status") != "FROZEN_PENDING_FULL_STAGE_A_AUTHORIZATION":
        raise runner.FullStageAV2Error("freeze status is not pending authorization")
    if freeze.get("executionPackageDigest") != runner._digest(runner.FULL_PACKAGE):
        raise runner.FullStageAV2Error("freeze package digest mismatch")
    if freeze.get("preregistrationDigest") != runner._digest(
        runner.FULL_PREREGISTRATION
    ):
        raise runner.FullStageAV2Error("freeze preregistration digest mismatch")
    for relative_path, expected in package["boundDigests"].items():
        try:
            actual = _blob_digest(_git_blob(commit, relative_path))
        except subprocess.CalledProcessError as error:
            raise runner.FullStageAV2Error(
                f"path is not present in freeze commit: {relative_path}"
            ) from error
        if actual != expected:
            raise runner.FullStageAV2Error(
                f"freeze commit blob digest mismatch: {relative_path}"
            )
    for relative_path, expected in {
        runner._relative(runner.FULL_PACKAGE): freeze["executionPackageDigest"],
        runner._relative(runner.FULL_PREREGISTRATION): freeze["preregistrationDigest"],
        runner._relative(runner.FULL_RUNTIME): freeze["runtimeConfigurationDigest"],
    }.items():
        if _blob_digest(_git_blob(commit, relative_path)) != expected:
            raise runner.FullStageAV2Error(
                f"freeze artifact blob digest mismatch: {relative_path}"
            )
    if (
        freeze.get("providerExecutionAuthorized") is not False
        or freeze.get("heldOutInspected") is not False
    ):
        raise runner.FullStageAV2Error("freeze opens execution or held-out custody")
    if freeze.get("authorization", {}).get("status") != "NOT_ISSUED":
        raise runner.FullStageAV2Error("authorization is already issued")
    return {
        "status": "PREAUTHORIZATION_READY_FULL_STAGE_A_V2",
        "experimentId": "s12-f-11",
        "commitSha": commit,
        "packageDigest": runner._digest(runner.FULL_PACKAGE),
        "freezeDigest": runner._digest(runner.FULL_FREEZE),
        "providerCalls": 48,
        "branchOutputs": 96,
        "zeroProviderCallsPerformed": True,
        "outputPathAbsent": not output_path.exists(),
        "providerExecutionAuthorized": False,
        "heldOutInspected": False,
        "stageBAuthorized": False,
        "candidateSelectionAuthorized": False,
        "promotionAuthorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), indent=2))
