"""Strict source-only validator for dense-hard candidate v2."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "dense-hard-source-payload.v2.json"
PROTOCOL = HERE / "dense-hard-source-only-protocol.v2.json"
SCHEMA = HERE / "dense-hard-candidate.v2.schema.json"
BUILD = HERE / "build_dense_hard_candidate_v2.py"
CANDIDATE = HERE / "dense-hard-candidate.v2.json"

TYPES = {"Task", "Requirement", "Constraint", "Risk", "System", "Project", "Document", "Question", "Decision", "Dataset", "Person", "Control", "Resource"}
PREDICATES = {"dependsOn", "implements", "blocks", "supports", "validates", "tracks", "constrains", "supersedes", "requires", "answers", "contains"}
MODES = {"none", "partial", "full"}


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def stable(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_anchor(errors: list[str], source: str, value: Any, where: str) -> tuple[int, int] | None:
    if not isinstance(value, dict) or set(value) != {"startOffset", "endOffset", "text"}:
        fail(errors, f"{where}: malformed anchor")
        return None
    start, end, text = value["startOffset"], value["endOffset"], value["text"]
    if not isinstance(start, int) or not isinstance(end, int) or not isinstance(text, str):
        fail(errors, f"{where}: anchor types")
        return None
    if start < 0 or end <= start or end > len(source):
        fail(errors, f"{where}: invalid half-open range [{start},{end})")
    elif source[start:end] != text:
        fail(errors, f"{where}: exact text mismatch")
    return start, end


def validate() -> list[str]:
    errors: list[str] = []
    source_packet = json.loads(SOURCE.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    if candidate.get("sourcePayloadDigest") != source_packet.get("payloadDigest"):
        fail(errors, "source payload digest mismatch")
    if candidate.get("protocolDigest") != protocol.get("protocolDigest"):
        fail(errors, "protocol digest mismatch")
    if candidate.get("sourceOnly") is not True or candidate.get("providerCalls") != 0:
        fail(errors, "source-only/provider-call guard failed")
    if candidate.get("goldIncluded") is not False or candidate.get("priorReviewsIncluded") is not False:
        fail(errors, "gold/prior-review guard failed")
    if candidate.get("scoring") is not False or candidate.get("review") is not False:
        fail(errors, "scoring/review guard failed")
    if candidate.get("agentCandidateCalls") != 28:
        fail(errors, "agentCandidateCalls must be 28")
    if candidate.get("candidateDigest") != digest(stable({**candidate, "candidateDigest": None})):
        fail(errors, "candidate digest mismatch")
    if candidate.get("codeDigest") != digest(BUILD.read_bytes()):
        fail(errors, "build code digest mismatch")
    records = {record["caseId"]: record for record in source_packet["records"]}
    responses = candidate.get("responses", [])
    if len(responses) != 28 or {item.get("caseId") for item in responses} != set(records):
        fail(errors, "responses must cover exactly the 28 source case IDs")
    for response in responses:
        case_id = response.get("caseId")
        if case_id not in records:
            continue
        source = records[case_id]["rawText"]
        if response.get("sourceDigest") != records[case_id]["sourceDigest"]:
            fail(errors, f"{case_id}: source digest mismatch")
        if response.get("scenarioId") != records[case_id]["scenarioId"]:
            fail(errors, f"{case_id}: scenario mismatch")
        entities = response.get("entities", [])
        relations = response.get("relations", [])
        quarantined = response.get("quarantined", [])
        entity_ids = [item.get("entityId") for item in entities]
        if len(set(entity_ids)) != len(entity_ids):
            fail(errors, f"{case_id}: duplicate entity IDs")
        occurrence_keys = [item.get("occurrenceKey") for item in entities]
        if len(set(occurrence_keys)) != len(occurrence_keys):
            fail(errors, f"{case_id}: occurrenceKey reused")
        ranges: dict[str, tuple[int, int]] = {}
        for item in entities:
            if item.get("type") not in TYPES:
                fail(errors, f"{case_id}: unreleased entity type")
            if item.get("entityId") in ranges:
                fail(errors, f"{case_id}: duplicate entity ID")
            span = check_anchor(errors, source, item.get("evidence"), f"{case_id}/{item.get('entityId')}")
            if span:
                ranges[item["entityId"]] = span
        registry = response.get("occurrenceRegistry", [])
        if len(registry) != len(entities):
            fail(errors, f"{case_id}: occurrence registry mismatch")
        for item, reg in zip(entities, registry, strict=False):
            if any(reg.get(key) != item.get(key) for key in ("occurrenceKey", "entityId", "label", "evidence")):
                fail(errors, f"{case_id}: occurrence registry entry mismatch")
        relation_ids: set[str] = set()
        for item in relations:
            relation_id = item.get("relationId")
            if relation_id in relation_ids:
                fail(errors, f"{case_id}: duplicate relation ID")
            relation_ids.add(relation_id)
            if item.get("predicate") not in PREDICATES:
                fail(errors, f"{case_id}: unreleased predicate")
            source_id, target_id = item.get("sourceEntityId"), item.get("targetEntityId")
            if source_id not in ranges or target_id not in ranges:
                fail(errors, f"{case_id}: relation endpoint does not reference a declared entity")
            evidence_span = check_anchor(errors, source, item.get("evidence"), f"{case_id}/{relation_id}/evidence")
            trigger_span = check_anchor(errors, source, item.get("triggerEvidence"), f"{case_id}/{relation_id}/trigger")
            if evidence_span and trigger_span and not (evidence_span[0] <= trigger_span[0] and trigger_span[1] <= evidence_span[1]):
                fail(errors, f"{case_id}/{relation_id}: trigger is outside evidence")
            if evidence_span and source_id in ranges and target_id in ranges:
                for endpoint, label in ((ranges[source_id], "source"), (ranges[target_id], "target")):
                    if not (evidence_span[0] <= endpoint[0] and endpoint[1] <= evidence_span[1]):
                        fail(errors, f"{case_id}/{relation_id}: {label} endpoint is outside evidence")
        for item in quarantined:
            if item.get("status") != "quarantined":
                fail(errors, f"{case_id}: quarantine status invalid")
            check_anchor(errors, source, item.get("evidence"), f"{case_id}/{item.get('assertionId')}/evidence")
            if "triggerEvidence" in item:
                check_anchor(errors, source, item["triggerEvidence"], f"{case_id}/{item.get('assertionId')}/trigger")
        mode = response.get("abstention", {}).get("mode")
        if mode not in MODES:
            fail(errors, f"{case_id}: invalid abstention mode")
        elif mode == "none" and quarantined:
            fail(errors, f"{case_id}: none mode cannot quarantine assertions")
        elif mode == "partial" and (not quarantined or not entities and not relations):
            fail(errors, f"{case_id}: partial mode requires finalized and quarantined content")
        elif mode == "full" and (entities or relations or not quarantined):
            fail(errors, f"{case_id}: full mode requires only quarantined content")
        proposition_ids = [item.get("assertionId") for item in response.get("propositionRegistry", [])]
        expected_ids = entity_ids + [item.get("relationId") for item in relations] + [item.get("assertionId") for item in quarantined]
        if proposition_ids != expected_ids:
            fail(errors, f"{case_id}: proposition registry does not enumerate response assertions")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("dense-hard v2 validation FAILED")
        print("\n".join(f"- {item}" for item in problems))
        sys.exit(1)
    print("dense-hard v2 validation PASSED: 28 cases, source-only, anchors/endpoints/quarantine/digests verified")
