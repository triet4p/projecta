"""Freeze a new source-only v5 payload from cases unused by v3 and v4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATOMIC = ROOT / "evaluation/sprint-12/corpus/v3-frozen/atomic-v3.frozen.v1.json"
OUTPUT = ROOT / "evaluation/sprint-12/internal-poc/s12-f-rf-blinded-source-payload.v5.json"
CASE_IDS = (
    "s12-a-4099", "s12-a-4107", "s12-a-4115", "s12-a-4123", "s12-a-4131", "s12-a-4139",
    "s12-a-4147", "s12-a-4155", "s12-a-4163", "s12-a-4171", "s12-a-4179", "s12-a-4187",
)


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def build_payload() -> dict[str, object]:
    atomic = json.loads(ATOMIC.read_text(encoding="utf-8"))
    by_id = {case["caseId"]: case for case in atomic["cases"]}
    records = []
    for case_id in CASE_IDS:
        source = by_id[case_id]["source"]
        records.append({"caseId": case_id, "scenarioId": by_id[case_id]["scenarioId"], "language": source["language"], "sourceDigest": source["contentDigest"], "rawText": source["rawText"]})
    payload: dict[str, object] = {
        "artifactVersion": "s12.f-rf.blinded-source-payload.v5",
        "status": "FROZEN_SOURCE_ONLY_FOR_CANDIDATE",
        "candidateModel": "gpt-5.6-luna", "reasoning": "high", "sourceOnly": True,
        "goldIncluded": False, "priorScoresIncluded": False, "priorReviewsIncluded": False,
        "providerCalls": 0, "heldOutInspection": False,
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
    payload["payloadDigest"] = _digest(payload)
    return payload


if __name__ == "__main__":
    payload = build_payload()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUTPUT.as_posix(), "records": len(payload["records"]), "payloadDigest": payload["payloadDigest"]}, sort_keys=True))
