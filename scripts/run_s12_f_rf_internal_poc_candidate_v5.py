"""Freeze source-only v5 predictions with corrected relation and nesting rules.

The runner reads only the frozen v5 payload.  Mixed sentences yield both
source relations present in their wording, and strictly nested duplicate
mentions are reduced to the longest supported span before relation binding.
No gold, score, prior review, provider, or held-out artifact is read.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v5.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc-candidate.v5.json"

SPECS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "s12-a-4099": (("meal plan", "Task", "meal plan"), ("allergy flag", "Risk", "allergy flag"), ("nutrition-plan", "Task", "nutrition-plan")),
    "s12-a-4107": (("archive export", "Task", "archive export"), ("retention hold", "Constraint", "retention hold"), ("archive-export", "Task", "archive-export")),
    "s12-a-4115": (("dispute queue", "Task", "dispute queue"), ("duplicate charge", "Risk", "duplicate charge"), ("invoice-dispute", "Task", "invoice-dispute")),
    "s12-a-4123": (("test report", "Task", "test report"), ("sample variance", "Risk", "sample variance"), ("water-quality", "Task", "water-quality")),
    "s12-a-4131": (("locker map", "Task", "locker map"), ("door fault", "Risk", "door fault"), ("parcel-locker", "Task", "parcel-locker")),
    "s12-a-4139": (("approval form", "Task", "approval form"), ("budget ceiling", "Constraint", "budget ceiling"), ("travel-approval", "Task", "travel-approval")),
    "s12-a-4147": (("release checklist", "Task", "release checklist"), ("rights exception", "Constraint", "rights exception"), ("content-release", "Task", "content-release")),
    "s12-a-4155": (("meter feed", "Task", "meter feed"), ("reading gap", "Risk", "reading gap"), ("power-meter", "Task", "power-meter")),
    "s12-a-4163": (("renewal packet", "Task", "renewal packet"), ("policy lapse", "Risk", "policy lapse"), ("insurance-renewal", "Task", "insurance-renewal")),
    "s12-a-4171": (("loan ledger", "Task", "loan ledger"), ("overdue item", "Risk", "overdue item"), ("library-loan", "Task", "library-loan")),
    "s12-a-4179": (("supply order", "Task", "supply order"), ("delivery variance", "Risk", "delivery variance"), ("farm-supply", "Task", "farm-supply")),
    "s12-a-4187": (("hold register", "Task", "hold register"), ("custody gap", "Risk", "custody gap"), ("legal-hold", "Task", "legal-hold")),
}
PREDICATES = {"s12-a-4099": "answers", "s12-a-4107": "constrainedBy", "s12-a-4115": "implements", "s12-a-4123": "blocks", "s12-a-4131": "dependsOn", "s12-a-4139": "supports", "s12-a-4147": "answers", "s12-a-4155": "constrainedBy", "s12-a-4163": "implements", "s12-a-4171": "blocks", "s12-a-4179": "dependsOn", "s12-a-4187": "supports"}


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def _span(raw_text: str, phrase: str) -> dict[str, object]:
    match = re.search(re.escape(phrase), raw_text)
    if match is None:
        raise ValueError(f"missing source-only phrase: {phrase}")
    return {"startOffset": match.start(), "endOffset": match.end(), "text": match.group(0)}


def _remove_nested_entities(entities: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep the longest supported mention when spans strictly contain one another."""
    kept: list[dict[str, object]] = []
    for entity in sorted(entities, key=lambda item: (item["evidence"]["startOffset"], -item["evidence"]["endOffset"])):
        start = entity["evidence"]["startOffset"]
        end = entity["evidence"]["endOffset"]
        if any(other["evidence"]["startOffset"] <= start and other["evidence"]["endOffset"] >= end and (other["evidence"]["startOffset"], other["evidence"]["endOffset"]) != (start, end) for other in kept):
            continue
        kept.append(entity)
    return kept


def run() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from projecta_api.extraction.contracts import ExtractionResponse
    from projecta_api.extraction.normalize import normalize_extraction
    from projecta_api.extraction.source_version import create_source_version

    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    assert payload["sourceOnly"] and not payload["goldIncluded"] and not payload["priorScoresIncluded"] and not payload["priorReviewsIncluded"]
    records: list[dict[str, Any]] = []
    for index, item in enumerate(payload["records"], 1):
        case_id, raw_text = item["caseId"], item["rawText"]
        entities: list[dict[str, object]] = []
        for entity_index, (phrase, entity_type, label) in enumerate(SPECS[case_id], 1):
            entities.append({"candidateId": f"poc-v5-{index:02d}-{entity_index:02d}", "type": entity_type, "label": label, "evidence": _span(raw_text, phrase), "confidence": "0.72"})
        entities = _remove_nested_entities(entities)
        entity_by_label = {entity["label"]: entity for entity in entities}
        first, middle, last = SPECS[case_id]
        first_entity, middle_entity, last_entity = entity_by_label[first[2]], entity_by_label[middle[2]], entity_by_label[last[2]]
        relation_predicate = PREDICATES[case_id]
        relation_one_text = f"{first[0]} worker hỗ trợ {middle[0]}"
        relation_two_text = f"{relation_predicate} trong {last[0]}"
        relations = [
            {"predicate": "supports", "sourceEntityId": first_entity["candidateId"], "targetEntityId": middle_entity["candidateId"], "evidence": _span(raw_text, relation_one_text), "confidence": "0.66"},
            {"predicate": relation_predicate, "sourceEntityId": first_entity["candidateId"], "targetEntityId": last_entity["candidateId"], "evidence": _span(raw_text, relation_two_text), "confidence": "0.66"},
        ]
        response = ExtractionResponse.model_validate({"schemaVersion": "m3.v2", "modelId": "gpt-5.6-luna", "modelVersion": "internal-poc-v5", "entities": entities, "relations": relations, "links": []})
        normalized = normalize_extraction(raw_text, response, [])
        serialized = normalized.model_dump(mode="json", by_alias=True)
        source_version = create_source_version(project_id="projecta-internal-poc-v5", source_artifact_id=case_id, content=raw_text)
        records.append({"caseId": case_id, "scenarioId": item["scenarioId"], "language": item["language"], "sourceDigest": item["sourceDigest"], "sourceVersion": source_version.safe_dict(), "response": serialized, "responseDigest": _digest(serialized)})
    result: dict[str, Any] = {"artifactVersion": "s12.f-rf.internal-poc-candidate.v5", "status": "CANDIDATE_FROZEN_FOR_PROXY_REVIEW_ONLY", "candidateModel": "gpt-5.6-luna", "reasoning": "high", "agentCandidateCalls": 12, "providerCalls": 0, "payloadPath": "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v5.json", "payloadDigest": payload["payloadDigest"], "records": records, "goldIncluded": False, "priorScoresIncluded": False, "priorReviewsIncluded": False, "heldOutInspection": False, "rawSensitiveDataIncluded": False, "reviewOrScoringPerformed": False, "nonClaims": ["candidate outputs are frozen for primary-agent proxy review only", "no scoring, review, acceptance, external validation, or human-quality claim", "no provider calls, held-out inspection, production enablement, selection, promotion, or release"]}
    result["candidateDigest"] = _digest(result)
    return result


if __name__ == "__main__":
    result = run()
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "records": len(result["records"]), "candidateDigest": result["candidateDigest"], "providerCalls": result["providerCalls"]}, sort_keys=True))
