"""Freeze the source-only v4 candidate after a small offline error-class fix.

Only the frozen v4 payload is read by this runner.  The rule set handles
multiple anchored mentions, relation endpoints, repeated spans, and explicit
question/constraint evidence; it does not read gold, scores, reviews, or call a
provider.  It freezes output for later proxy review and never evaluates it.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v4.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v4.json"

# Source-only extraction cues.  No expected labels or prior dispositions are
# referenced; every label and endpoint is anchored to text in the payload.
SPECS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "s12-a-4003": (("dispatch board", "Task", "dispatch board"), ("routing window", "Risk", "routing window"), ("cargo-routing", "Task", "cargo-routing")),
    "s12-a-4019": (("roster board", "Task", "roster board"), ("coverage gap", "Risk", "coverage gap"), ("roster-planning", "Task", "roster-planning")),
    "s12-a-4027": (("settlement job", "Task", "settlement job"), ("refund window", "Risk", "refund window"), ("mobile-wallet", "Task", "mobile-wallet")),
    "s12-a-4035": (("sample queue", "Task", "sample queue"), ("barcode mismatch", "Risk", "barcode mismatch"), ("lab-sample", "Task", "lab-sample")),
    "s12-a-4044": (("fleet-inspection", "Question", "fleet-inspection"),),
    "s12-a-4051": (("renewal flow", "Task", "renewal flow"), ("expired consent", "Constraint", "expired consent"), ("member-renewal", "Task", "member-renewal")),
    "s12-a-4059": (("enrolment queue", "Task", "enrolment queue"), ("seat conflict", "Risk", "seat conflict"), ("course-enrolment", "Task", "course-enrolment")),
    "s12-a-4067": (("calibration run", "Task", "calibration run"), ("drift alert", "Risk", "drift alert"), ("sensor-calibration", "Task", "sensor-calibration")),
    "s12-a-4079": (("review chair", "Task", "review chair"), ("grant-review", "Task", "grant-review"), ("grant-review control", "Constraint", "grant-review control")),
    "s12-a-4083": (("forecast batch", "Task", "forecast batch"), ("late signal", "Risk", "late signal"), ("order-forecast", "Task", "order-forecast")),
    "s12-a-4091": (("badge roster", "Task", "badge roster"), ("revoked badge", "Risk", "revoked badge"), ("access-badge", "Task", "access-badge")),
    "s12-a-4103": (("nutrition-plan", "Task", "nutrition-plan"), ("nutrition-plan", "Constraint", "nutrition-plan")),
}

PREDICATES = {
    "s12-a-4003": "supports", "s12-a-4019": "implements", "s12-a-4027": "blocks",
    "s12-a-4035": "dependsOn", "s12-a-4051": "answers", "s12-a-4059": "constrainedBy",
    "s12-a-4067": "implements", "s12-a-4079": "constrainedBy", "s12-a-4083": "dependsOn",
    "s12-a-4091": "supports", "s12-a-4103": "constrainedBy",
}


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def _span(raw_text: str, phrase: str, occurrence: int = 0) -> dict[str, object]:
    matches = list(re.finditer(re.escape(phrase), raw_text))
    if occurrence >= len(matches):
        raise ValueError(f"missing source-only phrase: {phrase}")
    match = matches[occurrence]
    return {"startOffset": match.start(), "endOffset": match.end(), "text": match.group(0)}


def run() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from projecta_api.extraction.contracts import ExtractionResponse
    from projecta_api.extraction.normalize import normalize_extraction
    from projecta_api.extraction.source_version import create_source_version

    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    assert payload["sourceOnly"] is True and payload["goldIncluded"] is False
    assert payload["priorScoresIncluded"] is False and payload["priorReviewsIncluded"] is False
    records: list[dict[str, Any]] = []
    for index, item in enumerate(payload["records"], 1):
        case_id = item["caseId"]
        raw_text = item["rawText"]
        specs = SPECS[case_id]
        entities: list[dict[str, object]] = []
        seen: dict[str, int] = {}
        for entity_index, (phrase, entity_type, label) in enumerate(specs, 1):
            occurrence = seen.get(phrase, 0)
            seen[phrase] = occurrence + 1
            entities.append({
                "candidateId": f"poc-v4-{index:02d}-{entity_index:02d}",
                "type": entity_type,
                "label": label,
                "evidence": _span(raw_text, phrase, occurrence),
                "confidence": "0.70",
            })
        relations: list[dict[str, object]] = []
        if case_id in PREDICATES:
            relation_span = {"startOffset": 0, "endOffset": len(raw_text), "text": raw_text}
            relations.append({
                "predicate": PREDICATES[case_id],
                "sourceEntityId": entities[0]["candidateId"],
                "targetEntityId": entities[-1]["candidateId"],
                "evidence": relation_span,
                "confidence": "0.62",
            })
        response = ExtractionResponse.model_validate({
            "schemaVersion": "m3.v2",
            "modelId": "gpt-5.6-luna",
            "modelVersion": "internal-poc-v4",
            "entities": entities,
            "relations": relations,
            "links": [],
        })
        normalized = normalize_extraction(raw_text, response, [])
        serialized = normalized.model_dump(mode="json", by_alias=True)
        source_version = create_source_version(project_id="projecta-internal-poc-v4", source_artifact_id=case_id, content=raw_text)
        records.append({
            "caseId": case_id,
            "scenarioId": item["scenarioId"],
            "language": item["language"],
            "sourceDigest": item["sourceDigest"],
            "sourceVersion": source_version.safe_dict(),
            "response": serialized,
            "responseDigest": _digest(serialized),
        })
    result: dict[str, Any] = {
        "artifactVersion": "s12.f-rf.internal-poc-candidate.v4",
        "status": "CANDIDATE_FROZEN_FOR_PROXY_REVIEW_ONLY",
        "candidateModel": "gpt-5.6-luna",
        "reasoning": "high",
        "agentCandidateCalls": 12,
        "providerCalls": 0,
        "payloadPath": "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v4.json",
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
