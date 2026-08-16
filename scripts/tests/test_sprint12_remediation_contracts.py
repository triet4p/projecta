"""Contract tests for the offline f09 remediation track."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "evaluation/sprint-12/harness"


def _read(name: str) -> dict:
    return json.loads((HARNESS / name).read_text(encoding="utf-8"))


def test_slice_thresholds_are_versioned_and_fail_closed() -> None:
    contract = _read("slice-threshold-contract.v1.json")
    assert contract["status"] == "FROZEN_FOR_NEXT_PREREGISTRATION_NO_PROVIDER"
    assert contract["primaryStatistic"] == "relationSemanticMicroF1"
    assert contract["secondaryStatistic"] == "relationSemanticMacroF1"
    assert contract["sliceGate"]["required"] is True
    assert contract["denominatorPolicy"]["zeroDenominator"].startswith(
        "NOT_APPLICABLE"
    )
    assert contract["providerCallsAuthorized"] is False


def test_trigger_contract_requires_candidate_quote_but_preserves_compatibility() -> None:
    contract = _read("relation-trigger-contract.v1.json")
    assert contract["schemaField"] == "triggerQuote"
    assert contract["schemaFieldOptionalForCompatibility"] is False
    assert contract["transport"] == "new-versioned-relation-evidence-envelope-not-m3.v2"
    assert contract["requiredForNextToolCandidate"] is True
    assert len(contract["requiredPredicates"]) == 7
    assert contract["providerCallsAuthorized"] is False


def test_f10_draft_binds_development_selection_and_shared_response_contract() -> None:
    optimization = ROOT / "evaluation/sprint-12/optimization"
    prereg = json.loads(
        (optimization / "s12-f-10-relation-evidence-shared-response-preregistration.draft.v1.json").read_text(
            encoding="utf-8"
        )
    )
    selection = json.loads(
        (optimization / "s12-f-10-case-selection.v1.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-manifest.v1.json").read_text(
            encoding="utf-8"
        )
    )
    development = {
        str(case["caseId"])
        for case in manifest["atomicCases"]
        if case.get("split") == "development"
    }
    case_ids = selection["caseIds"]
    assert prereg["status"] == "DRAFT_NOT_AUTHORIZED"
    assert len(case_ids) == 16 and set(case_ids) <= development
    assert selection["caseSelectionDigest"] == (
        "sha256:"
        + hashlib.sha256(
            json.dumps(case_ids, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert prereg["comparisonIntegrity"]["providerCallPerCasePair"] == 1
    assert prereg["executionPackage"]["providerCalls"] == 48
    assert prereg["executionPackage"]["branchOutputs"] == 96
    assert prereg["control"]["configuration"]["postProcessing"] != prereg["candidate"]["configuration"]["postProcessing"]
    assert prereg["control"]["configuration"]["model"] == prereg["candidate"]["configuration"]["model"]
    assert prereg["executionAuthorized"] is False
    assert prereg["heldOutInspected"] is False
