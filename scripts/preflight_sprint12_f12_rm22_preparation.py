#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Zero-call RM-22 preflight for the prepared S12-f-12 lineage."""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

PACKAGE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22-execution-package.v1.json"
PREREG = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22-prereg-draft.v1.json"
FREEZE = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm22-technical-freeze.v1.json"
SELECTION = ROOT / "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json"
ATOMIC_MANIFEST = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json"
OUTPUT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v1.json"

REQUIRED_BOUND_PATHS = frozenset(
    {
        "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-proposal.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-two-step-extraction-design-review.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts-review.v5.json",
        "evaluation/sprint-12/optimization/s12-f-12-offline-contracts.v5.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-1-entity-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-2-relation-envelope.schema.v2.json",
        "evaluation/sprint-12/harness/s12-f-12-oracle-fixtures.v5.json",
        "scripts/sprint12_f12_two_step_contracts_v5.py",
        "scripts/preflight_sprint12_f12_offline_contracts_v5.py",
        "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/scenario-v3.frozen.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/scenario-manifest.v1.json",
        "evaluation/sprint-12/corpus/v3-frozen/freeze-manifest.v1.json",
        "evaluation/sprint-12/optimization/s12-f-10-case-selection.v2.json",
        "evaluation/sprint-12/harness/metric-contract.v2.json",
        "evaluation/sprint-12/harness/slice-threshold-contract.v1.json",
        "evaluation/sprint-12/harness/relation-trigger-contract.v1.json",
        "evaluation/sprint-12/optimization/s12-f-08-pricing-deepseek-v4-flash.v1.json",
        "evaluation/sprint-12/optimization/s12-f-12-m3-prompt-v7-v2-two-step-extraction.v1.txt",
        "evaluation/sprint-12/harness/s12-f-12-runtime-configuration.v1.json",
        "evaluation/sprint-12/harness/s12-f-12-stage-a-report.schema.v1.json",
        "scripts/sprint12_f12_provider_adapter.py",
        "scripts/run_sprint12_f12_stage_a.py",
        "scripts/preflight_sprint12_f12_rm22_preparation.py",
        "evaluation/sprint-12/optimization/s12-f-12-rm22-prereg-draft.v1.json",
    }
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"artifact is not an object: {path}")
    return value


def _check_bound_digests(package: dict[str, Any]) -> None:
    bindings = package.get("boundDigests")
    if not isinstance(bindings, dict) or set(bindings) != REQUIRED_BOUND_PATHS:
        raise ValueError("RM-22 bound digest set is not exact")
    for relative, expected in bindings.items():
        path = ROOT / relative
        if not path.is_file() or _digest(path) != expected:
            raise ValueError(f"bound blob mismatch: {relative}")


def _check_case_and_denominators(prereg: dict[str, Any]) -> dict[str, Any]:
    selection = _load(SELECTION)
    manifest = _load(ATOMIC_MANIFEST)
    ids = list(selection.get("caseIds", []))
    rows = [row for row in manifest.get("atomicCases", []) if row.get("caseId") in ids]
    if len(ids) != 16 or len(set(ids)) != 16 or len(rows) != 16:
        raise ValueError("selection does not resolve to exactly 16 frozen development cases")
    if any(row.get("split") != "development" for row in rows):
        raise ValueError("selection includes a non-development case")
    profile = selection.get("selectionProfile")
    if profile != {
        "positiveRelationCases": 8,
        "abstentionRequiredCases": 4,
        "hardNegativeCases": 4,
        "journeysRepresented": ["J1", "J2", "J3", "J4", "J5", "J6"],
        "languagesRepresented": ["en", "ja", "mixed", "vi"],
    }:
        raise ValueError("selection profile is not the approved f12 profile")
    declared = prereg.get("denominators", {})
    if declared.get("caseRuns") != 48 or declared.get("goldRelationInstancesPerModelArm") != 24 or declared.get("goldAbstentionInstancesPerModelArm") != 12:
        raise ValueError("approved minimum denominators are not bound")
    named = declared.get("namedSliceMinimums")
    if not isinstance(named, dict) or named.get("all-development") != 48 or named.get("relation-positive") != 24 or named.get("abstention-required") != 12:
        raise ValueError("named slice denominator minimums are incomplete")
    return {
        "selectedCases": len(rows),
        "caseRuns": 48,
        "goldRelationInstancesPerModelArm": 24,
        "goldAbstentionInstancesPerModelArm": 12,
        "languageCaseCounts": {key: sum(row.get("language") == key for row in rows) for key in ("en", "ja", "mixed", "vi")},
        "journeyCaseCounts": {key: sum(row.get("journeyId") == key for row in rows) for key in ("J1", "J2", "J3", "J4", "J5", "J6")},
    }


def _check_cost(package: dict[str, Any], runtime: dict[str, Any]) -> None:
    if package.get("costCeilingUsd") != "10.00" or runtime.get("worstCaseCostUsd") != "1.17315072":
        raise ValueError("cost ceiling or worst-case runtime proof is not exact")
    expected = Decimal(144) * (Decimal(50000) * Decimal("0.14") + Decimal(4096) * Decimal("0.28")) / Decimal(1000000)
    if expected != Decimal("1.17315072") or expected >= Decimal("10.00"):
        raise ValueError("144-call cost proof does not fit the ceiling")


def _check_guarded_zero_call() -> None:
    from run_sprint12_f12_stage_a import F12StageAError, run_stage_a

    class SpyAdapter:
        calls = 0

        def capture_stage(self, **_: object) -> object:
            self.calls += 1
            raise AssertionError("provider capture was reached during no-auth preflight")

    spy = SpyAdapter()
    try:
        run_stage_a(provider_adapter=spy, authorization_path=None, output_path=OUTPUT)
    except F12StageAError as error:
        if "authorization" not in str(error):
            raise ValueError("unauthorized path failed for the wrong reason") from error
    else:
        raise ValueError("unauthorized path unexpectedly succeeded")
    if spy.calls != 0:
        raise ValueError("unauthorized path performed a provider call")


def run_preflight() -> dict[str, Any]:
    package = _load(PACKAGE)
    prereg = _load(PREREG)
    freeze = _load(FREEZE)
    runtime = _load(ROOT / "evaluation/sprint-12/harness/s12-f-12-runtime-configuration.v1.json")
    _check_bound_digests(package)
    if package.get("status") != "EXECUTION_PACKAGE_PREPARED_PENDING_RM23_OWNER_REVIEW":
        raise ValueError("package is not pending RM-23")
    if prereg.get("status") != "PREPARED_PENDING_RM23_OWNER_ISSUANCE_REVIEW" or prereg.get("providerExecutionAuthorized") is not False:
        raise ValueError("preregistration is not issuance-only")
    if freeze.get("status") != "TECHNICAL_FREEZE_PREPARED_PENDING_RM23_OWNER_REVIEW" or freeze.get("commitSha") is not None:
        raise ValueError("technical freeze is not commit-pending preparation")
    if package.get("providerCalls") != 144 or package.get("stage1ProviderCalls") != 48 or package.get("stage2ProviderCalls") != 96 or package.get("relationBranchOutputs") != 96:
        raise ValueError("provider schedule is not exact")
    if package.get("providerExecutionAuthorized") is not False or package.get("heldOutInspected") is not False:
        raise ValueError("execution governance is open")
    if PACKAGE.exists() and OUTPUT.exists():
        raise ValueError("prepared output path already exists")
    if list(ROOT.glob("evaluation/sprint-12/optimization/s12-f-12-*-authorization*.json")):
        raise ValueError("f12 authorization already exists")
    _check_cost(package, runtime)
    denominators = _check_case_and_denominators(prereg)
    _check_guarded_zero_call()
    return {
        "status": "F12_RM22_READY_ZERO_CALL_V1",
        "experimentId": "s12-f-12",
        "providerCalls": 0,
        "preparedProviderCalls": 144,
        "relationBranchOutputs": 96,
        "denominators": denominators,
        "providerExecutionAuthorized": False,
        "preregistrationIssued": False,
        "heldOutAccess": False,
        "reportPathExists": OUTPUT.exists(),
    }


if __name__ == "__main__":
    print(json.dumps(run_preflight(), indent=2, sort_keys=True))
