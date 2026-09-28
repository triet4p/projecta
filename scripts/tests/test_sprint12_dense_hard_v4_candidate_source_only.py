"""Regression tests for the public, source-only v4 candidate contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_s12_dense_hard_v4_candidate_source_only import main  # noqa: E402
from validate_s12_dense_hard_v4_candidate_source_only import validate  # noqa: E402


def test_builder_and_validator_cover_all_cases() -> None:
    main()
    result = validate()
    assert result["records"] == 32
    assert result["abstentions"] == {"none": 23, "partial": 4, "full": 5}
    assert result["quarantine"] == 10
    assert result["uncertainty"] == 2


def test_unicode_and_emoji_anchors_are_exact() -> None:
    main()
    candidate = __import__("json").loads((ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4/dense-hard-candidate.v4.json").read_text(encoding="utf-8"))
    source = __import__("json").loads((ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4/dense-hard-source-payload.v4.json").read_text(encoding="utf-8"))
    source_by_case = {record["caseId"]: record["rawText"] for record in source["records"]}
    candidate_by_case = {record["caseId"]: record for record in candidate["records"]}
    for case_id in ("dh4-011", "dh4-012"):
        text = source_by_case[case_id]
        for entity in candidate_by_case[case_id]["entities"]:
            evidence = entity["evidence"]
            assert text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"]


@pytest.mark.parametrize("case_id", ["dh4-029", "dh4-030", "dh4-031", "dh4-032"])
def test_full_abstention_has_no_safe_finalization(case_id: str) -> None:
    main()
    import json

    candidate = json.loads((ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4/dense-hard-candidate.v4.json").read_text(encoding="utf-8"))
    record = next(item for item in candidate["records"] if item["caseId"] == case_id)
    assert record["abstention"] == "full"
    assert not record["entities"]
    assert not record["relations"]
