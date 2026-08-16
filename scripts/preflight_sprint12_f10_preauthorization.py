#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic>=2,<3",
#     "pytest>=8,<9",
# ]
# ///
"""Pre-Approval-B validation for the final S12-f-10 package.

This is an integrity and reproducibility check only.  It never calls a
provider and it never creates authorization.  A missing commit binding is a
NO-GO, even when the current worktree happens to contain matching files.
"""

from __future__ import annotations

import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

from run_sprint12_next_tool_experiment import (
    FINAL_PACKAGE,
    FINAL_PRICING,
    ROOT,
    ExecutionPackageError,
    load_bound_development_cases,
    validate_final_execution_package,
)
from sprint12_pricing import file_digest, load_pricing_artifact

FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-10-execution-package-freeze.v4.json"
PREREGISTRATION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-relation-evidence-shared-response-preregistration.v3.json"
OUTPUT_PATH = ROOT / "evaluation/sprint-12/optimization/s12-f-10-stage-a-report.v4.json"
CANONICAL_TESTS = (
    "scripts/tests/test_sprint12_next_tool_runner.py",
    "scripts/tests/test_sprint12_f10_preauthorization_preflight.py",
    "apps/api/tests/test_relation_evidence_materializer.py",
    "apps/api/tests/test_relation_evidence_envelope.py",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _commit_is_ancestor(commit_sha: str) -> bool:
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


def _blob_digest(commit_sha: str, relative_path: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", "show", f"{commit_sha}:{relative_path}"),
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return "sha256:" + sha256(result.stdout).hexdigest()


def _canonical_tests_pass() -> bool:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(ROOT / "scripts"), str(ROOT / "apps" / "api" / "src"), environment.get("PYTHONPATH", ""))
    )
    try:
        subprocess.run(
            (
                "uv",
                "run",
                "--with",
                "pydantic>=2,<3",
                "--with",
                "pytest>=8,<9",
                "python",
                "-m",
                "pytest",
                "-q",
                *CANONICAL_TESTS,
            ),
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def build_preflight(*, run_tests: bool = False) -> dict[str, Any]:
    freeze = _load(FREEZE)
    package = _load(FINAL_PACKAGE)
    preregistration = _load(PREREGISTRATION)
    raw_commit_sha = freeze.get("commitSha")
    commit_sha = raw_commit_sha if isinstance(raw_commit_sha, str) else ""
    try:
        validate_final_execution_package(FINAL_PACKAGE, output_path=OUTPUT_PATH)
        package_integrity = True
    except (ExecutionPackageError, KeyError, TypeError, ValueError):
        package_integrity = False
    try:
        _, selected, profile = load_bound_development_cases()
        case_selection_reproducible = len(selected) == 16 and profile == {
            "relation-positive": 8,
            "abstention-required": 4,
            "relation-negative": 8,
            "hard-negative": 4,
        }
    except (ExecutionPackageError, KeyError, TypeError, ValueError):
        case_selection_reproducible = False
        profile = {}
    bound_digests = package.get("boundDigests", {})
    blob_checks = {
        str(path): _blob_digest(commit_sha, str(path)) == digest
        for path, digest in bound_digests.items()
    } if isinstance(bound_digests, dict) else {}
    arms = preregistration.get("control"), preregistration.get("candidate")
    schemas_match = (
        isinstance(arms[0], dict)
        and isinstance(arms[1], dict)
        and arms[0].get("configuration", {}).get("providerSchema") == "relation-evidence-envelope.v1"
        and arms[1].get("configuration", {}).get("providerSchema") == "relation-evidence-envelope.v1"
        and arms[0].get("configuration", {}).get("branchOutputSchema") == "m3.v2"
        and arms[1].get("configuration", {}).get("branchOutputSchema") == "m3.v2"
    )
    pricing = load_pricing_artifact(FINAL_PRICING)
    slice_contract = _load(ROOT / str(package.get("sliceContract", ""))) if package.get("sliceContract") else {}
    required_denominators = {
        "caseRuns",
        "missingOutput",
        "pairedComparison",
        "zeroDenominator",
    }
    denominator_policy = slice_contract.get("denominatorPolicy", {})
    slice_contract_complete = (
        slice_contract.get("status") == "FROZEN_FOR_NEXT_PREREGISTRATION_NO_PROVIDER"
        and set(slice_contract.get("sliceDimensions", []))
        == {
            "all-development",
            "relation-positive",
            "relation-negative",
            "abstention-required",
            "abstention-not-required",
            "journey",
            "language",
        }
        and required_denominators.issubset(denominator_policy)
        and isinstance(slice_contract.get("thresholds"), dict)
    )
    package_relative = str(FINAL_PACKAGE.relative_to(ROOT).as_posix())
    prereg_relative = str(PREREGISTRATION.relative_to(ROOT).as_posix())
    package_read_paths = {
        str(path)
        for path in bound_digests
        if isinstance(path, str)
    }
    package_read_paths.update(
        {
            str(package.get("authorizationContract", "")),
            str(package.get("metricContract", "")),
            str(package.get("caseSelection", "")),
            str(package.get("sliceContract", "")),
            str(package.get("pricingArtifact", "")),
        }
    )
    dataset = package.get("dataset", {})
    if isinstance(dataset, dict):
        package_read_paths.update(str(dataset.get(key, "")) for key in ("atomic", "scenario", "manifest"))
    package_read_paths.discard("")
    package_read_blob_checks = {
        path: _blob_digest(commit_sha, path) == file_digest(ROOT / path)
        for path in sorted(package_read_paths)
    }
    metric_contract_path = str(package.get("metricContract", ""))
    dataset_paths = package.get("dataset", {}) if isinstance(package.get("dataset"), dict) else {}
    checks = {
        "freezeStatus": freeze.get("status") == "FROZEN_PENDING_APPROVAL_A",
        "packageStatus": package.get("status") == "EXECUTION_PACKAGE_FROZEN_PENDING_AUTHORIZATION",
        "packageRunnerImplemented": package.get("executionRunnerImplemented") is True,
        "packageIntegrity": package_integrity,
        "packageDigestMatchesFreeze": freeze.get("executionPackageDigest") == file_digest(FINAL_PACKAGE),
        "preregistrationDigestMatchesFreeze": freeze.get("preregistrationDigest") == file_digest(PREREGISTRATION),
        "commitPresentInHead": _commit_is_ancestor(commit_sha),
        "freezeCommitShaBound": bool(commit_sha) and freeze.get("commitSha") == commit_sha,
        "packageBlobInCommit": _blob_digest(commit_sha, package_relative) == file_digest(FINAL_PACKAGE),
        "preregistrationBlobInCommit": _blob_digest(commit_sha, prereg_relative) == file_digest(PREREGISTRATION),
        "allBoundFilesInCommit": bool(blob_checks) and all(blob_checks.values()),
        "allPackageReadPathsInCommit": bool(package_read_blob_checks) and all(package_read_blob_checks.values()),
        "corpusBlobsInCommit": all(
            package_read_blob_checks.get(str(dataset_paths.get(key)), False)
            for key in ("atomic", "scenario", "manifest")
        ),
        "metricContractBlobInCommit": package_read_blob_checks.get(metric_contract_path, False),
        "providerSchemasMatch": schemas_match,
        "preregistrationStatusUnissued": preregistration.get("status") == "FINAL_PREREGISTRATION_DRAFT_NOT_ISSUED",
        "preregistrationExecutionUnauthorized": preregistration.get("providerExecutionAuthorized") is False,
        "authorizationContractBound": package.get("authorizationContract") == "evaluation/sprint-12/harness/s12-f-10-stage-a-authorization.schema.v2.json",
        "caseSelectionReproducible": case_selection_reproducible,
        "sliceLabelsAndDenominatorsBound": package.get("sliceContract") == "evaluation/sprint-12/harness/slice-threshold-contract.v1.json" and slice_contract_complete,
        "pricingBound": pricing.get("status") == "BOUND" and freeze.get("pricingDigest") == file_digest(FINAL_PRICING),
        "outputPathAvailable": not OUTPUT_PATH.exists(),
        "authorizationNotIssued": freeze.get("authorization", {}).get("status") == "NOT_ISSUED",
        "providerExecutionUnauthorized": freeze.get("providerExecutionAuthorized") is False,
        "heldOutUninspected": freeze.get("heldOutInspected") is False and preregistration.get("heldOutInspected") is False,
        "exactCostCeilingBound": package.get("costCeilingUsd") == "10.00" and preregistration.get("pricingContract", {}).get("costCeilingUsd") == "10.00",
        "invalidEvidenceGateBound": preregistration.get("hardGates", {}).get("invalidEvidence") == 0,
        "canonicalTestsPass": _canonical_tests_pass() if run_tests else False,
    }
    status = "PREAUTHORIZATION_READY" if all(checks.values()) else "NO_GO_PREAUTHORIZATION_PREFLIGHT"
    return {
        "reportVersion": "s12.s12-f-10.preauthorization-preflight.v3",
        "status": status,
        "checks": checks,
        "caseSelectionProfile": profile,
        "boundBlobChecks": blob_checks,
        "packageReadBlobChecks": package_read_blob_checks,
        "commitSha": commit_sha or None,
        "providerCallsPerformed": False,
        "providerExecutionAuthorized": False,
        "heldOutInspected": False,
        "authorizationIssued": False,
    }


def main() -> None:
    print(json.dumps(build_preflight(run_tests=True), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
