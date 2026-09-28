"""Create the frozen source-only payload for the internal F-RF candidate v3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-internal-poc.v1.json"
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v3.json"


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def build_payload() -> dict[str, object]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    atomic = json.loads(ATOMIC.read_text(encoding="utf-8"))
    by_id = {case["caseId"]: case for case in atomic["cases"]}
    records = []
    for scenario_id, case_id in zip(
        protocol["datasetBinding"]["scenarioIds"],
        protocol["datasetBinding"]["representativeCaseIds"],
        strict=True,
    ):
        case = by_id[case_id]
        source = case["source"]
        records.append(
            {
                "caseId": case_id,
                "scenarioId": scenario_id,
                "language": source["language"],
                "sourceDigest": source["contentDigest"],
                "rawText": source["rawText"],
            }
        )
    payload: dict[str, object] = {
        "artifactVersion": "s12.f-rf.blinded-source-payload.v3",
        "status": "FROZEN_SOURCE_ONLY_FOR_CANDIDATE",
        "candidateModel": "gpt-5.6-luna",
        "reasoning": "high",
        "sourceOnly": True,
        "goldIncluded": False,
        "priorScoresIncluded": False,
        "priorReviewsIncluded": False,
        "providerCalls": 0,
        "heldOutInspection": False,
        "requiredOutputSchema": {
            "schemaVersion": "m3.v2",
            "entities": "candidateId,type,label,evidence{startOffset,endOffset,text},confidence",
            "relations": "predicate,sourceEntityId,targetEntityId,evidence,confidence",
            "links": "mention,targetEntityId,evidence,confidence",
            "abstention": "abstentionReason when no safe candidate is supportable",
            "anchorRule": "zero-based Unicode code-point half-open offsets; exact evidence text",
        },
        "records": records,
    }
    payload["payloadDigest"] = _digest({k: v for k, v in payload.items() if k != "payloadDigest"})
    return payload


if __name__ == "__main__":
    payload = build_payload()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUTPUT.as_posix(), "records": len(payload["records"]), "payloadDigest": payload["payloadDigest"]}, sort_keys=True))
