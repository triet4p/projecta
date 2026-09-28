"""Fail-closed validation for the frozen dense-hard v4 source-only candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v4"
SOURCE = V4 / "dense-hard-source-payload.v4.json"
PROTOCOL = V4 / "dense-hard-source-only-protocol.v4.json"
CONTRACT = V4 / "dense-hard-evaluator-contract.v4.json"
SCHEMA = V4 / "dense-hard-candidate.v4.schema.json"
CANDIDATE = V4 / "dense-hard-candidate.v4.json"


def stable(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(stable(value)).hexdigest()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate() -> dict[str, Any]:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(candidate), key=lambda error: list(error.path))
    check(not errors, "; ".join(error.message for error in errors))
    check(len(candidate["records"]) == 32, "candidate must contain all 32 records")
    check(candidate["bindings"]["sourcePayloadDigest"] == source["payloadDigest"], "source payload binding mismatch")
    check(candidate["bindings"]["protocolDigest"] == protocol["protocolDigest"], "protocol binding mismatch")
    check(candidate["bindings"]["evaluatorContractDigest"] == contract["contractDigest"], "contract binding mismatch")
    without_digest = {key: value for key, value in candidate.items() if key != "candidateDigest"}
    check(candidate["candidateDigest"] == digest(without_digest), "candidate digest mismatch")

    by_case = {record["caseId"]: record for record in source["records"]}
    seen: set[str] = set()
    counts = {"none": 0, "partial": 0, "full": 0}
    quarantine_count = 0
    uncertainty_count = 0
    for record in candidate["records"]:
        case_id = record["caseId"]
        check(case_id in by_case, f"unknown case {case_id}")
        check(case_id not in seen, f"duplicate case {case_id}")
        seen.add(case_id)
        source_record = by_case[case_id]
        check(record["scenarioId"] == source_record["scenarioId"], f"scenario mismatch: {case_id}")
        check(record["sourceDigest"] == source_record["sourceDigest"], f"source digest mismatch: {case_id}")
        text = source_record["rawText"]
        occurrences = {entity["occurrenceId"]: entity for entity in record["entities"]}
        for entity in record["entities"]:
            evidence = entity["evidence"]
            check(evidence["endOffset"] > evidence["startOffset"], f"empty entity span: {case_id}")
            check(text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"], f"entity anchor mismatch: {case_id}")
        for relation in record["relations"]:
            check(relation["sourceOccurrenceId"] in occurrences, f"ungrounded source endpoint: {case_id}")
            check(relation["targetOccurrenceId"] in occurrences, f"ungrounded target endpoint: {case_id}")
            evidence = relation["triggerEvidence"]
            check(text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"], f"relation trigger mismatch: {case_id}")
            check(all(evidence["text"] in text[evidence["startOffset"] : evidence["endOffset"]] for _ in [0]), f"trigger not contained: {case_id}")
        for item in record["quarantine"]:
            evidence = item["evidence"]
            check(text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"], f"quarantine anchor mismatch: {case_id}")
            if "triggerEvidence" in item:
                trigger = item["triggerEvidence"]
                check(text[trigger["startOffset"] : trigger["endOffset"]] == trigger["text"], f"quarantine trigger mismatch: {case_id}")
                check(trigger["text"] in evidence["text"], f"quarantine trigger not contained: {case_id}")
        abstention = record["abstention"]
        counts[abstention] += 1
        quarantine_count += len(record["quarantine"])
        uncertainty_count += len(record["uncertainty"])
        safe_count = len(record["entities"]) + len(record["relations"])
        if abstention == "none":
            check(not record["quarantine"], f"none abstention cannot quarantine: {case_id}")
        elif abstention == "partial":
            check(safe_count > 0 and record["quarantine"], f"partial abstention requires safe and unsafe propositions: {case_id}")
        else:
            check(safe_count == 0, f"full abstention requires zero safe propositions: {case_id}")
    check(seen == set(by_case), "candidate does not cover exactly the source cases")
    return {"records": len(seen), "abstentions": counts, "quarantine": quarantine_count, "uncertainty": uncertainty_count, "candidateDigest": candidate["candidateDigest"]}


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
