"""Contract tests for Sprint 12 language metadata validation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sprint12_language_validator", ROOT / "scripts/sprint12_language_validator.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CORPUS = ROOT / "evaluation/sprint-12/corpus"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_inference_distinguishes_english_vietnamese_japanese_and_mixed() -> None:
    assert MODULE.infer_language("The requirement is ready for review.")["language"] == "en"
    assert MODULE.infer_language("Đã hoàn tất kiểm thử luồng.")["language"] == "vi"
    assert MODULE.infer_language("チェックアウトテストは完了した。 ")["language"] == "ja"
    assert MODULE.infer_language("Release có risk bị trễ.")["language"] == "mixed"


def test_historical_v2_fixture_reports_mismatch_and_excludes_unreviewed_slices() -> None:
    report = MODULE.validate_paths(
        CORPUS / "atomic-development-validation.v2.json",
        CORPUS / "manifest.v2.json",
        CORPUS / "qa/qa-report.v2.json",
    )
    assert report["reportVersion"] == "s12.language-validator.v2"
    assert report["status"] == "BLOCKED_LANGUAGE_METADATA"
    assert report["atomic"]["mismatchCount"] > 0
    assert any(row["caseId"] == "s12-a-0187" for row in report["atomic"]["mismatches"])
    assert report["review"]["qualifiedReview"] is False
    assert set(report["review"]["excludedSlicesWithoutQualifiedReview"]) == {
        "en",
        "ja",
        "mixed",
        "vi",
    }
    assert report["gates"]["eligibleLanguageSlices"] == []
    assert report["readScope"]["testPayloadRead"] is False

    serialized = json.dumps(report, ensure_ascii=False)
    assert "rawText" not in serialized
    assert "From review 187" not in serialized


def test_test_payload_is_rejected_if_accidentally_supplied() -> None:
    case = {
        "caseId": "test-1",
        "split": "test",
        "source": {"language": "en", "rawText": "The requirement is ready."},
    }
    with pytest.raises(MODULE.LanguageValidationError, match="held-out"):
        MODULE.analyze_cases([case], qualified_review=False)
