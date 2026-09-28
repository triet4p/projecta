"""Fail-closed validator for the dense-hard v3 source-only candidate."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3"
SOURCE_PATH = PACKET / "dense-hard-source-payload.v3.json"
PROTOCOL_PATH = PACKET / "dense-hard-source-only-protocol.v3.json"
CONTRACT_PATH = PACKET / "dense-hard-evaluator-contract.v3.json"
CANDIDATE_PATH = PACKET / "dense-hard-candidate.v3.json"
SCHEMA_PATH = PACKET / "dense-hard-candidate.v3.schema.json"
FROZEN_BUILDER_DIGEST = "sha256:34a351e651c5eda20661f1fc24d53767ac558402f05fd81cf754de45add1310d"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def fail(message: str) -> None:
    raise AssertionError(message)


def within(inner: dict[str, Any], outer: dict[str, Any]) -> bool:
    return outer["startOffset"] <= inner["startOffset"] < inner["endOffset"] <= outer["endOffset"]


def exact(raw: str, span: dict[str, Any]) -> None:
    start = span["startOffset"]
    end = span["endOffset"]
    if start < 0 or end <= start or raw[start:end] != span["text"]:
        fail(f"invalid exact anchor {span!r}")


def validate() -> dict[str, Any]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    errors = sorted(Draft202012Validator(schema).iter_errors(candidate), key=lambda error: list(error.path))
    if errors:
        fail("schema: " + "; ".join(error.message for error in errors[:5]))
    if candidate["sourcePayloadDigest"] != source["payloadDigest"]:
        fail("source payload digest binding mismatch")
    if candidate["protocolDigest"] != protocol["protocolDigest"]:
        fail("protocol digest binding mismatch")
    if candidate["evaluatorContractDigest"] != contract["contractDigest"]:
        fail("evaluator contract digest binding mismatch")
    # Bind to the digest frozen into the candidate packet.  Do not compare it
    # with a mutable working-tree builder: the candidate is immutable and its
    # source-only record is the evaluation input.
    if candidate["buildCodeDigest"] != FROZEN_BUILDER_DIGEST:
        fail("frozen build code digest mismatch")
    candidate_without_digest = copy.deepcopy(candidate)
    candidate_without_digest.pop("candidateDigest")
    if candidate["candidateDigest"] != digest(canonical(candidate_without_digest)):
        fail("candidate digest mismatch")

    source_by_id = {item["caseId"]: item for item in source["records"]}
    if len(source_by_id) != 30 or len(candidate["records"]) != 30:
        fail("candidate must contain exactly 30 source records")
    seen_cases: set[str] = set()
    allowed_reasons = set(protocol["quarantinePolicy"]["reasons"])
    allowed_types = set(protocol["finiteEntityTypes"])
    allowed_predicates = set(protocol["finiteRelationPredicates"])
    for record in candidate["records"]:
        case_id = record["caseId"]
        if case_id in seen_cases or case_id not in source_by_id:
            fail(f"unexpected or duplicate case {case_id}")
        seen_cases.add(case_id)
        source_record = source_by_id[case_id]
        if record["scenarioId"] != source_record["scenarioId"] or record["sourceDigest"] != source_record["sourceDigest"]:
            fail(f"source identity mismatch in {case_id}")
        raw = source_record["rawText"]
        entity_occurrences: set[tuple[int, int, str]] = set()
        for entity in record["entities"]:
            occurrence = entity["occurrence"]
            exact(raw, occurrence)
            if entity["label"] != occurrence["text"] or entity["type"] not in allowed_types:
                fail(f"entity label/type mismatch in {case_id}")
            key = (occurrence["startOffset"], occurrence["endOffset"], occurrence["text"])
            if key in entity_occurrences:
                fail(f"duplicate entity occurrence in {case_id}")
            entity_occurrences.add(key)
        for relation in record["relations"]:
            if relation["predicate"] not in allowed_predicates:
                fail(f"non-finite predicate in {case_id}")
            source_occurrence = relation["sourceOccurrence"]
            target_occurrence = relation["targetOccurrence"]
            evidence = relation["evidence"]
            trigger = relation["triggerEvidence"]
            exact(raw, source_occurrence)
            exact(raw, target_occurrence)
            exact(raw, evidence)
            exact(raw, trigger)
            if not within(source_occurrence, evidence) or not within(target_occurrence, evidence) or not within(trigger, evidence):
                fail(f"relation grounding failure in {case_id}")
            if (source_occurrence["startOffset"], source_occurrence["endOffset"], source_occurrence["text"]) not in entity_occurrences:
                fail(f"relation source occurrence not registered in {case_id}")
            if (target_occurrence["startOffset"], target_occurrence["endOffset"], target_occurrence["text"]) not in entity_occurrences:
                fail(f"relation target occurrence not registered in {case_id}")
        for item in record["quarantine"]:
            if item["reasonCode"] not in allowed_reasons:
                fail(f"non-protocol quarantine reason in {case_id}")
            exact(raw, item["evidence"])
        finalized = len(record["entities"]) + len(record["relations"])
        quarantined = len(record["quarantine"])
        if record["abstention"] == "none" and (finalized == 0 or quarantined != 0):
            fail(f"none abstention matrix violation in {case_id}")
        if record["abstention"] == "partial" and (finalized == 0 or quarantined == 0):
            fail(f"partial abstention matrix violation in {case_id}")
        if record["abstention"] == "full" and (finalized != 0 or quarantined == 0):
            fail(f"full abstention matrix violation in {case_id}")
    if seen_cases != set(source_by_id):
        fail("candidate does not cover every source case")
    return {
        "candidateDigest": candidate["candidateDigest"],
        "records": len(candidate["records"]),
        "finalizedEntities": sum(len(record["entities"]) for record in candidate["records"]),
        "finalizedRelations": sum(len(record["relations"]) for record in candidate["records"]),
        "quarantined": sum(len(record["quarantine"]) for record in candidate["records"]),
        "fullAbstentions": sum(record["abstention"] == "full" for record in candidate["records"]),
        "partialAbstentions": sum(record["abstention"] == "partial" for record in candidate["records"]),
        "noneAbstentions": sum(record["abstention"] == "none" for record in candidate["records"]),
        "agentCandidateCalls": candidate["agentCandidateCalls"],
        "providerCalls": candidate["providerCalls"],
        "goldUsed": candidate["goldUsed"],
        "priorReviewUsed": candidate["priorReviewUsed"],
        "scoringPerformed": candidate["scoringPerformed"],
    }


if __name__ == "__main__":
    try:
        print(json.dumps(validate(), ensure_ascii=False, sort_keys=True))
    except (AssertionError, json.JSONDecodeError, OSError) as error:
        print(f"dense-hard-v3 candidate validation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
