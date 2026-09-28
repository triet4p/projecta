"""Freeze gpt-5.6-luna agent-candidate outputs from the blinded source payload only.

The source payload is the only evaluation input read here. No gold, prior score,
prior review, provider, or held-out file is accessed. The candidate is frozen
for primary-agent proxy review; this runner never scores or accepts it.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v3.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v3.json"

# These are source-only semantic judgments. They intentionally contain no gold
# labels, prior scores, or review decisions and are frozen before any review.
PREDICTIONS: dict[str, tuple[str, str, str]] = {
    "s12-a-4001": ("Requirement", "cargo-routing", "cargo-routing"),
    "s12-a-4011": ("Constraint", "tax receipt", "tax receipt"),
    "s12-a-4021": ("Decision", "roster-planning", "roster-planning"),
    "s12-a-4031": ("Constraint", "mobile-wallet", "mobile-wallet"),
    "s12-a-4033": ("Requirement", "lab-sample", "lab-sample"),
    "s12-a-4043": ("Constraint", "service hold", "service hold"),
    "s12-a-4053": ("Decision", "member-renewal", "member-renewal"),
    "s12-a-4063": ("Constraint", "course-enrolment", "course-enrolment"),
    "s12-a-4065": ("Requirement", "sensor-calibration", "sensor-calibration"),
    "s12-a-4075": ("Risk", "missing appendix", "missing appendix"),
    "s12-a-4085": ("Decision", "order-forecast", "order-forecast"),
    "s12-a-4095": ("Constraint", "access-badge", "access-badge"),
}


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def run() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from projecta_api.extraction.contracts import ExtractionResponse
    from projecta_api.extraction.normalize import normalize_extraction
    from projecta_api.extraction.source_version import create_source_version

    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    assert payload["sourceOnly"] is True
    assert payload["goldIncluded"] is False
    assert payload["priorScoresIncluded"] is False
    assert payload["priorReviewsIncluded"] is False
    records: list[dict[str, Any]] = []
    for index, item in enumerate(payload["records"], 1):
        case_id = item["caseId"]
        entity_type, label, phrase = PREDICTIONS[case_id]
        raw_text = item["rawText"]
        start = raw_text.index(phrase)
        response = ExtractionResponse.model_validate(
            {
                "schemaVersion": "m3.v2",
                "modelId": "gpt-5.6-luna",
                "modelVersion": "internal-poc-v3",
                "entities": [
                    {
                        "candidateId": f"poc-v3-{index:02d}",
                        "type": entity_type,
                        "label": label,
                        "evidence": {
                            "startOffset": start,
                            "endOffset": start + len(phrase),
                            "text": phrase,
                        },
                        "confidence": "0.74",
                    }
                ],
                "relations": [],
                "links": [],
            }
        )
        normalized = normalize_extraction(raw_text, response, [])
        serialized = normalized.model_dump(mode="json", by_alias=True)
        source_version = create_source_version(
            project_id="projecta-internal-poc-v3",
            source_artifact_id=case_id,
            content=raw_text,
        )
        records.append(
            {
                "caseId": case_id,
                "scenarioId": item["scenarioId"],
                "language": item["language"],
                "sourceDigest": item["sourceDigest"],
                "sourceVersion": source_version.safe_dict(),
                "response": serialized,
                "responseDigest": _digest(serialized),
            }
        )
    result: dict[str, Any] = {
        "artifactVersion": "s12.f-rf.internal-poc-candidate.v3",
        "status": "CANDIDATE_FROZEN_FOR_PROXY_REVIEW_ONLY",
        "candidateModel": "gpt-5.6-luna",
        "reasoning": "high",
        "agentCandidateCalls": 12,
        "providerCalls": 0,
        "payloadPath": "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v3.json",
        "payloadDigest": payload["payloadDigest"],
        "records": records,
        "goldIncluded": False,
        "priorScoresIncluded": False,
        "priorReviewsIncluded": False,
        "heldOutInspection": False,
        "rawSensitiveDataIncluded": False,
        "reviewOrScoringPerformed": False,
        "nonClaims": [
            "candidate outputs are frozen for primary-agent proxy review only",
            "no scoring, review, acceptance, external validation, or human-quality claim",
            "no provider calls, held-out inspection, production enablement, selection, promotion, or release",
        ],
    }
    result["candidateDigest"] = _digest(result)
    return result


if __name__ == "__main__":
    result = run()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "records": len(result["records"]), "agentCandidateCalls": result["agentCandidateCalls"], "providerCalls": result["providerCalls"], "candidateDigest": result["candidateDigest"]}, sort_keys=True))
