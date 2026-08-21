#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""RM-22A zero-call preflight with corpus-derived denominators."""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PACKAGE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22a-execution-package.v2.json"
)
PREREG = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22a-issuance-draft.v2.json"
)
FREEZE = (
    ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22a-technical-freeze.v2.json"
)
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
SELECTION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v2.json"

REQUIRED_BOUND_PATHS = frozenset(
    {
        "evaluation/sprint-12/optimization/s12-f-12-rm23-owner-review.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v5.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts-review.v5.json",
        "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-review.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/scenario-v3.frozen.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/scenario-manifest.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/freeze-manifest.v1.json",
        "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json",
        "evaluation/sprint-12/harness/metric-contract.v2.json",
        "evaluation/sprint-12/harness/slice-threshold-contract.v1.json",
        "evaluation/sprint-12/harness/relation-trigger-contract.v1.json",
        "evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-m3-prompt-v7-v2-two-step-extraction.v1.txt",
        "evaluation/sprint-12/harness/s12-f-12-runtime-configuration.v1.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v2.json",
        "scripts/sprint12_f12_two_step_contracts_v5.py",
        "scripts/sprint12_f12_provider_adapter_v2.py",
        "scripts/run_sprint12_f12_stage_a_v2.py",
        "scripts/preflight_sprint12_f12_rm22a.py",
        "scripts/tests/test_sprint12_f12_rm22a_execution.py",
        "evaluation/sprint-12/optimization/s12-f-12-rm22a-issuance-draft.v2.json",
    }
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def derive_denominators(
    *, atomic_path: Path = ATOMIC, selection_path: Path = SELECTION, runs: int = 3
) -> dict[str, Any]:
    corpus = _load(atomic_path)
    selection = _load(selection_path)
    ids = list(selection.get("caseIds", []))
    by_id = {str(case["caseId"]): case for case in corpus.get("cases", [])}
    cases = [by_id.get(str(case_id)) for case_id in ids]
    if len(ids) != 16 or len(set(ids)) != 16 or any(case is None for case in cases):
        raise ValueError("selection does not resolve to 16 frozen cases")
    selected = [case for case in cases if case is not None]
    if any(case.get("split") != "development" for case in selected):
        raise ValueError("selection contains non-development gold")
    positive = [case for case in selected if len(case["gold"]["relations"]) > 0]
    abstention = [
        case for case in selected if bool(case["gold"]["abstention"]["required"])
    ]
    language_cases = {
        language: sum(case["source"]["language"] == language for case in selected)
        for language in ("en", "ja", "mixed", "vi")
    }
    journey_cases = {
        journey: sum(case["journeyId"] == journey for case in selected)
        for journey in ("J1", "J2", "J3", "J4", "J5", "J6")
    }
    return {
        "selectedDevelopmentCases": len(selected),
        "positiveRelationCases": len(positive),
        "goldRelationInstancesPerRun": sum(
            len(case["gold"]["relations"]) for case in selected
        ),
        "abstentionRequiredCases": len(abstention),
        "goldAbstentionInstancesPerRun": len(abstention),
        "caseRuns": len(selected) * runs,
        "relationInstancesAcrossRuns": sum(
            len(case["gold"]["relations"]) for case in selected
        )
        * runs,
        "abstentionInstancesAcrossRuns": len(abstention) * runs,
        "namedSliceDenominators": {
            "all-development": len(selected) * runs,
            "relation-positive": sum(
                len(case["gold"]["relations"]) for case in positive
            )
            * runs,
            "relation-negative": len(abstention) * runs,
            "abstention-required": len(abstention) * runs,
            "abstention-not-required": (len(selected) - len(abstention)) * runs,
            "journey": {key: value * runs for key, value in journey_cases.items()},
            "language": {key: value * runs for key, value in language_cases.items()},
        },
    }


def _verify_bindings(package: dict[str, Any]) -> None:
    bindings = package.get("boundDigests")
    if not isinstance(bindings, dict) or set(bindings) != REQUIRED_BOUND_PATHS:
        raise ValueError("RM-22A binding set is not exact")
    for relative, expected in bindings.items():
        path = ROOT / relative
        if not path.is_file() or _digest(path) != expected:
            raise ValueError(f"bound blob mismatch: {relative}")


def _verify_zero_call() -> None:
    from run_sprint12_f12_stage_a_v2 import F12StageAV2Error, run_stage_a

    class Spy:
        calls = 0

        def capture_stage(self, **_: object) -> object:
            self.calls += 1
            raise AssertionError("provider capture reached unauthorized preflight")

    spy = Spy()
    try:
        run_stage_a(provider_adapter=spy, authorization_path=None, output_path=OUTPUT)
    except F12StageAV2Error as error:
        if "authorization" not in str(error):
            raise ValueError(
                "unauthorized path failed for an unexpected reason"
            ) from error
    else:
        raise ValueError("unauthorized path unexpectedly succeeded")
    if spy.calls != 0:
        raise ValueError("unauthorized path performed a provider call")


def run_preflight() -> dict[str, Any]:
    package = _load(PACKAGE)
    prereg = _load(PREREG)
    freeze = _load(FREEZE)
    _verify_bindings(package)
    derived = derive_denominators()
    if prereg.get("denominators") != derived:
        raise ValueError("preregistration denominators do not match frozen gold")
    if (
        package.get("providerCalls") != 144
        or package.get("relationBranchOutputs") != 96
        or package.get("executionRunnerImplemented") is not True
    ):
        raise ValueError("package schedule or runner binding is not executable")
    if (
        package.get("providerExecutionAuthorized") is not False
        or prereg.get("providerExecutionAuthorized") is not False
        or freeze.get("providerExecutionAuthorized") is not False
    ):
        raise ValueError("execution governance is open")
    if freeze.get("commitSha") is not None or freeze.get(
        "executionPackageDigest"
    ) != _digest(PACKAGE):
        raise ValueError("technical freeze lineage is not preparation-only and exact")
    if OUTPUT.exists():
        raise ValueError("v2 output already exists")
    if list(
        ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-authorization*.json")
    ):
        raise ValueError("f12 authorization already exists")
    expected_cost = (
        Decimal(144)
        * (Decimal(50000) * Decimal("0.14") + Decimal(4096) * Decimal("0.28"))
        / Decimal(1_000_000)
    )
    if expected_cost != Decimal("1.17315072") or expected_cost >= Decimal("10.00"):
        raise ValueError("cost proof is not exact")
    _verify_zero_call()
    return {
        "status": "F12_RM22A_READY_ZERO_CALL_V2",
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
