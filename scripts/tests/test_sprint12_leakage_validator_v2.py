"""Contract tests for the fail-closed Sprint 12 leakage validator v2."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_leakage_validator", ROOT / "scripts/sprint12_leakage_validator.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CORPUS = ROOT / "evaluation/sprint-12/corpus"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_canonicalizer_removes_generator_markers_ids_numbers_and_punctuation() -> None:
    left = "Decision 101: approve scope. Evidence marker aa; distinguishing phrase aa."
    right = "decision 202 approve scope"
    assert MODULE.canonicalize_source(left) == MODULE.canonicalize_source(right)
    assert MODULE.contains_generator_marker(left) is True


def test_historical_v2_fixture_is_blocked_without_reading_test_payload() -> None:
    report = MODULE.validate_paths(
        CORPUS / "atomic-development-validation.v2.json",
        CORPUS / "scenario-development-validation.v2.json",
        CORPUS / "manifest.v2.json",
    )
    assert report["reportVersion"] == "s12.leakage-validator.v2"
    assert report["status"] == "BLOCKED_KNOWN_LEAKAGE"
    assert report["readScope"]["testPayloadRead"] is False
    assert report["readScope"]["testPayloadStatus"] == "not-available-custody"
    assert report["atomic"]["generatorMarkerCaseCount"] == 160
    assert report["atomic"]["crossSplitNormalizedTemplateClusters"]
    assert report["scenarios"]["reusedSourceLineageGroups"]
    assert report["scenarios"]["conflictingGoldGroups"]
    assert report["gates"]["fullSplitLeakage"] is False

    serialized = json.dumps(report, ensure_ascii=False)
    assert "rawText" not in serialized
    assert "Evidence marker" not in serialized
    assert "distinguishing phrase" not in serialized


def test_validator_catches_cross_split_template_and_exact_content_reuse() -> None:
    cases = [
        {
            "caseId": "dev-1",
            "split": "development",
            "source": {
                "rawText": "Approve item 101.",
                "contentDigest": "sha256:one",
            },
        },
        {
            "caseId": "val-1",
            "split": "validation",
            "source": {
                "rawText": "approve item 202",
                "contentDigest": "sha256:two",
            },
        },
        {
            "caseId": "val-2",
            "split": "validation",
            "source": {
                "rawText": "Approve item 101.",
                "contentDigest": "sha256:one",
            },
        },
    ]
    result = MODULE.analyze_atomic_cases(cases)
    assert result["pass"] is False
    assert result["crossSplitNormalizedTemplateClusters"]
    assert result["crossSplitExactContentDuplicateClusters"]


def test_test_payload_is_rejected_if_accidentally_supplied() -> None:
    case = {
        "caseId": "test-1",
        "split": "test",
        "source": {"rawText": "sealed", "contentDigest": "sha256:sealed"},
    }
    try:
        MODULE.analyze_atomic_cases([case])
    except MODULE.LeakageValidationError as error:
        assert "held-out" in str(error)
    else:
        raise AssertionError("test payload must be rejected")
