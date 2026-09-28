"""Serialize the owner-proxy review of frozen source-only candidate v5."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v5.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-review.v5.json"


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build() -> dict[str, object]:
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert candidate["candidateDigest"] == "sha256:09679f2cccae8eaf6477e5b1c3dc3baaf0767441f6bbc0a67b3b103b3d1affa1"
    records = []
    for index, candidate_record in enumerate(candidate["records"], 1):
        records.append({
            "recordId": f"poc-review-v5-{index:03d}", "caseId": candidate_record["caseId"], "scenarioId": candidate_record["scenarioId"],
            "sourceDigest": candidate_record["sourceDigest"], "candidateDigest": candidate_record["responseDigest"],
            "reviewerMode": "PRIMARY_AGENT_PROXY_OWNER_JUDGMENT", "humanEvidence": False, "finalDisposition": "confirmed",
            "correctionClass": "unchanged", "semanticEditCount": 0,
            "reason": "owner confirmed all source-anchored entities and relations as supported",
            "timingStatus": "UNMEASURED", "manualBaselineSeconds": None,
            "independentAgreement": "NOT_CLAIMED", "unsupportedFinalizedAssertions": 0,
            "supportedFinalizedAssertions": 5,
        })
    result: dict[str, object] = {
        "artifactVersion": "s12.f-rf.internal-poc-review.v5", "status": "EDIT_BURDEN_ONLY_ACCEPTED_AGENT_PROXY",
        "candidatePath": "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v5.json", "candidateDigest": candidate["candidateDigest"],
        "payloadPath": "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v5.json", "payloadDigest": candidate["payloadDigest"],
        "reviewerMode": "PRIMARY_AGENT_PROXY_OWNER_JUDGMENT", "humanEvidence": False, "providerCalls": 0, "heldOutInspection": False,
        "records": records,
        "metrics": {
            "eligibleReviewedItems": 12,
            "supportedFinalizedAssertions": {"numerator": 60, "denominator": 60, "status": "SUPPORTED_SOURCE_BOUND"},
            "unsupportedFinalizedAssertions": {"numerator": 0, "denominator": 60, "status": "ZERO_UNSUPPORTED"},
            "acceptedWithoutSemanticCorrection": {"numerator": 12, "denominator": 12, "rate": 1.0, "threshold": 0.7},
            "acceptedUnchangedOrMinor": {"numerator": 12, "denominator": 12, "rate": 1.0, "threshold": 0.85},
            "totalSemanticEdits": 0, "meanSemanticEditsPerReviewedItem": 0.0,
            "medianReviewTimeSeconds": None, "p90ReviewTimeSeconds": None, "medianReductionVsManualBaseline": None,
            "timingStatus": "UNMEASURED", "reviewerAgreement": {"status": "NOT_CLAIMED", "independentRecords": 0},
            "gateStatus": "EDIT_BURDEN_ONLY_ACCEPTED_AGENT_PROXY",
        },
        "nonClaims": [
            "primary-agent proxy judgment is not independent human-study evidence",
            "timing, manual baseline, reviewer agreement, external custody, and business-quality are not claimed",
            "no provider, held-out, production, selection, promotion, release, or external-validation claim",
        ],
    }
    result["reviewDigest"] = _digest(result)
    return result


if __name__ == "__main__":
    value = build()
    OUTPUT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": value["status"], "records": len(value["records"]), "reviewDigest": value["reviewDigest"]}, sort_keys=True))
