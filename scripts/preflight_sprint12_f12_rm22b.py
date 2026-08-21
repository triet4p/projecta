#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""RM-22B zero-call preflight for exact commit and measurement custody."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_sprint12_f12_stage_a_v3 import (
    FREEZE,
    OUTPUT,
    PACKAGE,
    PREREG,
    _json_at_commit,
    _verify_exact_commit,
    load,
    run_stage_a,
)

REQUIRED_SLICE_LABELS = (
    "all-development",
    "relation-positive",
    "relation-negative",
    "abstention-required",
    "abstention-not-required",
    "J1",
    "J2",
    "J3",
    "J4",
    "J5",
    "J6",
    "en",
    "ja",
    "mixed",
    "vi",
)


def _verify_zero_call() -> None:
    class Spy:
        calls = 0

        def capture_stage(self, **_: object) -> object:
            self.calls += 1
            raise AssertionError("provider capture reached zero-call preflight")

    spy = Spy()
    try:
        run_stage_a(provider_adapter=spy, authorization_path=None, output_path=OUTPUT)
    except RuntimeError as error:
        if "authorization" not in str(error):
            raise ValueError(
                "unauthorized path failed for an unexpected reason"
            ) from error
    else:
        raise ValueError("unauthorized path unexpectedly succeeded")
    if spy.calls != 0:
        raise ValueError("unauthorized preflight performed a provider call")


def _derive_denominators_at_commit(commit_sha: str) -> dict[str, Any]:
    corpus = _json_at_commit(
        commit_sha, "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
    )
    selection = _json_at_commit(
        commit_sha, "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
    )
    ids = list(selection.get("caseIds", []))
    cases = [case for case in corpus.get("cases", []) if case.get("caseId") in ids]
    if len(cases) != 16 or any(case.get("split") != "development" for case in cases):
        raise ValueError(
            "exact-commit corpus selection is not the 16 development cases"
        )
    positive = [case for case in cases if case["gold"]["relations"]]
    abstention = [case for case in cases if case["gold"]["abstention"]["required"]]
    languages = {
        language: sum(case["source"]["language"] == language for case in cases) * 3
        for language in ("en", "ja", "mixed", "vi")
    }
    journeys = {
        journey: sum(case["journeyId"] == journey for case in cases) * 3
        for journey in ("J1", "J2", "J3", "J4", "J5", "J6")
    }
    relation_instances = sum(len(case["gold"]["relations"]) for case in cases) * 3
    return {
        "selectedDevelopmentCases": 16,
        "positiveRelationCases": len(positive),
        "goldRelationInstancesPerRun": sum(
            len(case["gold"]["relations"]) for case in cases
        ),
        "abstentionRequiredCases": len(abstention),
        "goldAbstentionInstancesPerRun": len(abstention),
        "caseRuns": 48,
        "relationInstancesAcrossRuns": relation_instances,
        "abstentionInstancesAcrossRuns": len(abstention) * 3,
        "namedSliceDenominators": {
            "all-development": 48,
            "relation-positive": relation_instances,
            "relation-negative": len(abstention) * 3,
            "abstention-required": len(abstention) * 3,
            "abstention-not-required": (16 - len(abstention)) * 3,
            "journey": journeys,
            "language": languages,
        },
    }


def run_preflight() -> dict[str, Any]:
    package = load(PACKAGE)
    prereg = load(PREREG)
    freeze = load(FREEZE)
    derived = _derive_denominators_at_commit(str(package.get("commitSha")))
    if prereg.get("denominators") != derived:
        raise ValueError("RM-22B preregistration denominators do not match frozen gold")
    if package.get("commitSha") != freeze.get("commitSha") or not package.get(
        "commitSha"
    ):
        raise ValueError("RM-22B package/freeze exact commit is absent or inconsistent")
    bindings = package.get("boundDigests")
    exact_paths = package.get("exactCommitBoundPaths")
    if (
        not isinstance(bindings, dict)
        or not isinstance(exact_paths, list)
        or not exact_paths
    ):
        raise ValueError("RM-22B exact-commit binding set is incomplete")
    _verify_exact_commit(
        package["commitSha"], {str(path): bindings[path] for path in exact_paths}
    )
    if (
        package.get("providerCalls") != 144
        or package.get("relationBranchOutputs") != 96
    ):
        raise ValueError("RM-22B schedule is not exact")
    hard_gates = package.get("hardGates")
    required_hard_gates = {
        "schemaInvalid",
        "invalidEvidence",
        "missingOutput",
        "endpointContractFailure",
        "sharedConfigurationMismatch",
        "retryCount",
        "pricingFailure",
        "rawSensitiveDataIncluded",
        "heldOutInspected",
    }
    if not isinstance(hard_gates, dict) or set(hard_gates) != required_hard_gates:
        raise ValueError("RM-22B hard-gate binding is incomplete")
    if package.get("approvedThresholds") != prereg.get("approvedThresholds"):
        raise ValueError("RM-22B thresholds are not identically bound")
    labels = [item.get("label") for item in prereg.get("requiredSlices", [])]
    if labels != list(REQUIRED_SLICE_LABELS):
        raise ValueError("RM-22B required slice binding is incomplete")
    if (
        freeze.get("executionPackageDigest")
        != "sha256:" + __import__("hashlib").sha256(PACKAGE.read_bytes()).hexdigest()
    ):
        raise ValueError("RM-22B package digest is not bound by freeze")
    if (
        freeze.get("preregistrationDigest")
        != "sha256:" + __import__("hashlib").sha256(PREREG.read_bytes()).hexdigest()
    ):
        raise ValueError("RM-22B preregistration digest is not bound by freeze")
    if OUTPUT.exists() or list(
        ROOT.glob(
            "evaluation/sprint-12/optimization/s12-f-12-rm22b-*-authorization*.json"
        )
    ):
        raise ValueError("RM-22B output or authorization already exists")
    expected_cost = (
        Decimal(144)
        * (Decimal(50000) * Decimal("0.14") + Decimal(4096) * Decimal("0.28"))
        / Decimal(1_000_000)
    )
    if expected_cost != Decimal("1.17315072") or expected_cost >= Decimal("10.00"):
        raise ValueError("RM-22B cost proof is not exact")
    _verify_zero_call()
    return {
        "status": "F12_RM22B_READY_ZERO_CALL_V3",
        "experimentId": "s12-f-12",
        "providerCalls": 0,
        "preparedProviderCalls": 144,
        "relationBranchOutputs": 96,
        "derivedDenominators": derived,
        "providerExecutionAuthorized": False,
        "heldOutAccess": False,
        "reportPathExists": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), ensure_ascii=False, indent=2, sort_keys=True))
