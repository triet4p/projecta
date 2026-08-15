"""Checks for the owner-delegated Sprint 12 AI annotation track."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "evaluation/sprint-12/pilot"
CORPUS = ROOT / "evaluation/sprint-12/corpus"

SPEC = importlib.util.spec_from_file_location(
    "sprint12_annotation_review", ROOT / "scripts/review_sprint12_annotation.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_owner_delegated_annotation_review_is_complete_and_nonhuman() -> None:
    assert MODULE.validate_review() == {
        "status": "PASS_OWNER_DELEGATED_AI_ANNOTATION_TRACK",
        "pilotAtomicCases": 20,
        "pilotScenarios": 3,
        "freshRerunCases": 12,
        "humanEvidence": False,
    }


def test_fresh_rerun_is_disjoint_from_pilot_and_digest_bound() -> None:
    pilot = read_json(PILOT / "atomic-pilot.v1.json")
    fresh = read_json(PILOT / "fresh-rerun.v1.json")
    corpus = read_json(CORPUS / "atomic-development-validation.v1.json")
    corpus_by_id = {case["caseId"]: case for case in corpus["cases"]}
    assert not (
        {item["caseId"] for item in fresh["caseReviews"]}
        & {case["caseId"] for case in pilot["cases"]}
    )
    for item in fresh["caseReviews"]:
        assert item["goldDigest"] == MODULE.digest(
            corpus_by_id[item["caseId"]]["gold"]
        )


def test_ai_review_does_not_claim_independent_human_evidence() -> None:
    review = read_json(PILOT / "owner-delegated-ai-review.v1.json")
    qa = read_json(CORPUS / "qa/qa-report.v1.json")
    assert review["reviewerKind"] == "ai-agent"
    assert review["humanEvidence"] is False
    assert qa["ownerDelegatedAiReviewPresent"] is True
    assert qa["independentLabelsPresent"] is False
