#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Run offline preflight for the next-tool execution-package draft."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sprint12_pricing import file_digest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-next-tool-execution-package-draft.v1.json"


def read_package() -> dict[str, Any]:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))


def build_preflight() -> dict[str, Any]:
    package = read_package()
    digest_checks = {
        path: digest == file_digest(ROOT / path)
        for path, digest in package["boundDigests"].items()
    }
    checks = {
        "allBoundDigestsMatch": all(digest_checks.values()),
        "sharedResponsePrimitiveBound": digest_checks.get(
            "scripts/shared_response_pairing.py", False
        ),
        "sliceThresholdContractBound": digest_checks.get(
            "evaluation/sprint-12/harness/slice-threshold-contract.v1.json", False
        ),
        "triggerContractBound": digest_checks.get(
            "evaluation/sprint-12/harness/relation-trigger-contract.v1.json", False
        ),
        "caseSelectionBound": digest_checks.get(
            "evaluation/sprint-12/optimization/s12-f-10-case-selection.v1.json",
            False,
        ),
        "preregistrationDraftBound": digest_checks.get(
            "evaluation/sprint-12/optimization/s12-f-10-relation-evidence-shared-response-preregistration.draft.v1.json",
            False,
        ),
        "executionRunnerImplemented": package["executionRunnerImplemented"],
        "commitBound": bool(package.get("commitSha")),
        "authorizationIssued": package["providerExecutionAuthorized"],
        "heldOutInspected": package["heldOutInspected"],
    }
    return {
        "reportVersion": "s12.next-tool.remediation-preflight.v1",
        "status": (
            "READY_FOR_COMMIT_FREEZE"
            if all(checks.values())
            else "NO_GO_PENDING_EXECUTION_PACKAGE_COMMIT_AND_RUNNER"
        ),
        "providerCallsPerformed": False,
        "providerExecutionAuthorized": False,
        "checks": checks,
        "digestChecks": digest_checks,
        "packageArtifact": PACKAGE.name,
        "packageDigest": file_digest(PACKAGE),
    }


def main() -> None:
    print(json.dumps(build_preflight(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
