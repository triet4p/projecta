#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Offline zero-call preflight for the S12-RM-24 authorization preparation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm24-preparation.v1.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
sys.path.insert(0, str(ROOT / "scripts"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def _root_path(path_text: str) -> Path:
    path = ROOT / path_text
    if not path.is_file():
        raise ValueError(f"required artifact is missing: {path_text}")
    return path


def _assert_digest(binding: dict[str, Any]) -> None:
    path = _root_path(str(binding["path"]))
    if binding["digest"] != _digest(path):
        raise ValueError(f"digest mismatch: {binding['path']}")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def run_preflight(*, require_clean_tree: bool = True) -> dict[str, Any]:
    preparation = _load(PREPARATION)
    if preparation.get("status") != "PREPARED_PENDING_RM25_OWNER_AUTHORIZATION":
        raise ValueError("RM-24 preparation status is not pending RM-25")
    if preparation.get("experimentId") != "s12-f-12":
        raise ValueError("RM-24 experimentId is not exact")
    if preparation.get("taskId") != "S12-RM-24":
        raise ValueError("RM-24 taskId is not exact")
    if preparation.get("providerExecutionAuthorized") is not False:
        raise ValueError("RM-24 must not authorize provider execution")
    if preparation.get("providerCallsPerformedAtPreparation") != 0:
        raise ValueError("RM-24 preparation must record zero provider calls")

    current = _load(_root_path(preparation["currentState"]["path"]))
    if preparation["currentState"]["digest"] != _digest(_root_path(preparation["currentState"]["path"])):
        raise ValueError("current-state digest mismatch")
    if current.get("status") != "G5_F12_ISSUED_PROVIDER_AUTHORIZATION_PENDING":
        raise ValueError("current-state status has moved beyond RM-24")
    if current.get("experimentState", {}).get("providerCallsPerformed") != 0:
        raise ValueError("current-state records provider calls")

    g5 = _load(_root_path(preparation["g5Packet"]["path"]))
    _assert_digest(preparation["g5Packet"])
    if g5.get("status") != "G5_F12_ISSUED_PROVIDER_AUTHORIZATION_PENDING":
        raise ValueError("G5 packet is not the current issued-pending packet")

    transition = _load(_root_path(preparation["issuanceTransition"]["path"]))
    _assert_digest(preparation["issuanceTransition"])
    if transition.get("status") != preparation["issuanceTransition"]["status"]:
        raise ValueError("issuance transition status mismatch")
    if transition.get("currentDecisionState", {}).get("providerExecutionAuthorized") is not False:
        raise ValueError("issuance transition authorizes provider execution")

    owner_review = _load(_root_path(preparation["ownerReview"]["path"]))
    _assert_digest(preparation["ownerReview"])
    if owner_review.get("status") != preparation["ownerReview"]["status"]:
        raise ValueError("RM-23F owner-review status mismatch")
    if owner_review.get("decision", {}).get("providerExecutionAuthorized") is not False:
        raise ValueError("RM-23F owner review authorizes provider execution")

    lineage = preparation["issuedLineage"]
    execution_commit = lineage["executionCommit"]
    if len(execution_commit) != 40 or _git("rev-parse", execution_commit) != execution_commit:
        raise ValueError("exact execution commit is unavailable")
    _git("merge-base", "--is-ancestor", execution_commit, "HEAD")
    if transition.get("issuedLineage", {}).get("executionCommit") != execution_commit:
        raise ValueError("transition execution commit mismatch")
    if owner_review.get("reviewedLineage", {}).get("executionCommit") != execution_commit:
        raise ValueError("owner-review execution commit mismatch")
    for key in ("preregistration", "executionPackage", "technicalFreeze"):
        binding = lineage[key]
        _assert_digest(binding)
        if key == "executionPackage":
            package = _load(_root_path(binding["path"]))
            if package.get("commitSha") != execution_commit:
                raise ValueError("package execution commit mismatch")
            if package.get("providerExecutionAuthorized") is not False:
                raise ValueError("package authorizes provider execution")
            if package.get("providerCalls") != 144 or package.get("relationBranchOutputs") != 96:
                raise ValueError("package call or branch bounds mismatch")
            if package.get("retryPolicy") != "none" or package.get("outputOverwrite") is not False:
                raise ValueError("package retry/overwrite policy mismatch")
            if package.get("outputPath") != preparation["executionBounds"]["outputPath"]:
                raise ValueError("package output path mismatch")
            if package.get("costCeilingUsd") != preparation["executionBounds"]["costCeilingUsd"]:
                raise ValueError("package cost ceiling mismatch")
        elif key == "preregistration":
            prereg = _load(_root_path(binding["path"]))
            if prereg.get("executionCommitSha") != execution_commit:
                raise ValueError("preregistration execution commit mismatch")
        else:
            freeze = _load(_root_path(binding["path"]))
            if freeze.get("commitSha") != execution_commit:
                raise ValueError("freeze execution commit mismatch")
            if freeze.get("executionPackageDigest") != lineage["executionPackage"]["digest"]:
                raise ValueError("freeze package digest mismatch")
            if freeze.get("preregistrationDigest") != lineage["preregistration"]["digest"]:
                raise ValueError("freeze preregistration digest mismatch")

    for binding in preparation["exactBindings"].values():
        _assert_digest(binding)
    runtime = _load(_root_path(preparation["exactBindings"]["runtimeConfiguration"]["path"]))
    if runtime.get("apiKeyStored") is not False or runtime.get("providerPayloadStored") is not False:
        raise ValueError("runtime configuration stores secret or provider payload")

    bounds = preparation["executionBounds"]
    if bounds != {
        "providerCalls": 144,
        "stage1ProviderCalls": 48,
        "stage2ProviderCalls": 96,
        "relationBranchOutputs": 96,
        "requiredSchemaValidResponses": 144,
        "requiredUsageValidResponses": 144,
        "expectedPricedCalls": 144,
        "retryPolicy": "none",
        "retryAuthorized": False,
        "outputPath": "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json",
        "outputOverwrite": False,
        "outputOverwriteAuthorized": False,
        "worstCaseCostUsd": "1.17315072",
        "costCeilingUsd": "10.00",
    }:
        raise ValueError("RM-24 execution bounds are not exact")
    if any(preparation["governanceLocks"].values()):
        raise ValueError("RM-24 expanded governance authority")
    if OUTPUT.exists():
        raise ValueError("Stage A report output already exists")
    if require_clean_tree and _git("status", "--porcelain=v1"):
        raise ValueError("working tree must be clean for RM-24 preflight")

    return {
        "status": "S12_RM24_READY_ZERO_CALL_PENDING_RM25",
        "experimentId": "s12-f-12",
        "preparationScope": "S12-RM-24",
        "executionCommit": execution_commit,
        "providerCalls": 0,
        "providerExecutionAuthorized": False,
        "outputPathAbsent": True,
        "workingTreeClean": not bool(_git("status", "--porcelain=v1")),
        "heldOutInspected": False,
        "nextGate": "S12-RM-25_OWNER_REVIEW_AND_OPTIONAL_ONE_RUN_AUTHORIZATION",
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
