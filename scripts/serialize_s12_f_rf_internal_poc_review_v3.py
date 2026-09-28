"""Serialize the primary-agent proxy judgments for frozen candidate v3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v3.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v3.json"

JUDGMENTS = (
        ("confirmed", "unchanged", 0, "confirmed: source-supported candidate"),
        ("confirmed", "major", 5, "mixed relation sentence omits source/target/context entities and explicit relation(s), and extracted target type lacks sufficient support"),
        ("confirmed", "unchanged", 0, "confirmed: source-supported candidate"),
        ("confirmed", "major", 3, "repeated constrainedBy Vietnamese sentence omits separate anchored endpoints/constraint relationship and is incomplete"),
        ("confirmed", "unchanged", 0, "confirmed: source-supported candidate"),
        ("confirmed", "major", 5, "mixed relation sentence omits source/target/context entities and explicit relation(s), and extracted target type lacks sufficient support"),
        ("confirmed", "unchanged", 0, "confirmed: source-supported candidate"),
        ("confirmed", "major", 3, "repeated constrainedBy Vietnamese sentence omits separate anchored endpoints/constraint relationship and is incomplete"),
        ("confirmed", "unchanged", 0, "confirmed: source-supported candidate"),
        ("confirmed", "major", 5, "mixed relation sentence omits source/target/context entities and explicit relation(s), and extracted target type lacks sufficient support"),
        ("confirmed", "unchanged", 0, "confirmed: source-supported candidate"),
        ("confirmed", "major", 3, "repeated constrainedBy Vietnamese sentence omits separate anchored endpoints/constraint relationship and is incomplete"),
)


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build() -> dict[str, object]:
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert candidate["candidateDigest"] == "sha256:fbe412d85bc06d6aa6edf1a68ab26146123dd2fa35308e31abf9542e39f2afaa"
    records = []
    for index, (candidate_record, (disposition, correction_class, edit_count, reason)) in enumerate(
        zip(candidate["records"], JUDGMENTS, strict=True), 1
    ):
        records.append(
            {
                "recordId": f"poc-review-v3-{index:03d}",
                "caseId": candidate_record["caseId"],
                "scenarioId": candidate_record["scenarioId"],
                "sourceDigest": candidate_record["sourceDigest"],
                "candidateDigest": candidate_record["responseDigest"],
                "reviewerMode": "PRIMARY_AGENT_PROXY_OWNER_JUDGMENT",
                "humanEvidence": False,
                "finalDisposition": disposition,
                "correctionClass": correction_class,
                "semanticEditCount": edit_count,
                "reason": reason,
                "timingStatus": "UNMEASURED",
                "manualBaselineSeconds": None,
                "independentAgreement": "NOT_APPLICABLE_NO_INDEPENDENT_REVIEWER",
                "unsupportedFinalizedAssertions": 0,
            }
        )
    result: dict[str, object] = {
        "artifactVersion": "s12.f-rf.internal-poc-review.v3",
        "status": "POC_FAILED_ACCEPTANCE_RATE",
        "candidatePath": "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v3.json",
        "candidateDigest": candidate["candidateDigest"],
        "reviewerMode": "PRIMARY_AGENT_PROXY_OWNER_JUDGMENT",
        "humanEvidence": False,
        "providerCalls": 0,
        "heldOutInspection": False,
        "records": records,
        "metrics": {
            "eligibleReviewedItems": 12,
            "acceptedWithoutSemanticCorrection": {"numerator": 6, "rate": 0.5, "threshold": 0.7},
            "acceptedUnchangedOrMinor": {"numerator": 6, "rate": 0.5, "threshold": 0.85},
            "meanSemanticEditsPerReviewedItem": 2.0,
            "medianReviewTimeSeconds": None,
            "p90ReviewTimeSeconds": None,
            "medianReductionVsManualBaseline": None,
            "reviewerAgreement": {"status": "NOT_APPLICABLE_BLOCKS_GATE", "independentRecords": 0},
            "unsupportedFinalizedAssertions": {"numerator": 0, "denominator": 0, "status": "NOT_APPLICABLE_BLOCKS_GATE"},
            "gateStatus": "FAIL_ACCEPTANCE_RATE",
        },
        "nonClaims": [
            "owner-proxy review is not external, independent, blinded, or human-study evidence",
            "timing and manual baseline were unmeasured; reviewer agreement is unavailable",
            "no RM-68 acceptance, business-quality, provider, held-out, production, selection, promotion, or release claim",
        ],
    }
    result["reviewDigest"] = _digest(result)
    return result


if __name__ == "__main__":
    value = build()
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": value["status"], "records": len(value["records"]), "reviewDigest": value["reviewDigest"]}, sort_keys=True))
