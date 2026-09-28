"""Fail-closed validator and generic source-only guard for dense-hard v2.

The benchmark validator opens private gold/manifest only to validate the
authoring packet. The response guard accepts a source record and a proposed
response, never a candidate artifact, and enforces occurrence, type, relation,
abstention, anchor, and quarantine rules without using v1 case content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v2"
V1_PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v1"
SOURCE_NAME = "dense-hard-source-payload.v2.json"
GOLD_NAME = "dense-hard-gold.v2.json"
MANIFEST_NAME = "dense-hard-evaluator-manifest.v2.json"
PROTOCOL_NAME = "dense-hard-source-only-protocol.v2.json"
LINEAGE_NAME = "dense-hard-v2-lineage.v1.json"
CANDIDATE_NAME = "dense-hard-candidate.v2.json"
EVALUATION_NAME = "dense-hard-evaluation.v2.json"
ADJUDICATION_NAME = "dense-hard-evaluation-adjudication.v2.1.json"
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

POST_EVALUATION_NAMES = {
    "build_dense_hard_candidate_v2.py",
    "dense-hard-candidate.v2.json",
    "dense-hard-candidate.v2.schema.json",
    "validate_dense_hard_candidate_v2.py",
    "test_dense_hard_candidate_v2.py",
    "dense-hard-evaluation.v2.json",
    "dense-hard-evaluation.v2.schema.json",
    "dense-hard-evaluation-adjudication.v2.1.json",
    "dense-hard-evaluation-adjudication.v2.1.schema.json",
}


class ProtocolGuardError(ValueError):
    """A source-only response violates the generic v2 protocol."""


def canonical_digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(value: dict[str, Any], schema_path: Path) -> None:
    schema = _read(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{schema_path.name}: {list(errors[0].path)}: {errors[0].message}")


def _source_slice(text: str, evidence: dict[str, Any]) -> str:
    start, end = evidence["startOffset"], evidence["endOffset"]
    if start < 0 or end <= start or end > len(text) or text[start:end] != evidence["text"]:
        raise ValueError("evidence is not an exact Unicode half-open source span")
    return text[start:end]


def _sentence_set(text: str) -> set[str]:
    sentences = re.split(r"[.!?。！？]+", text)
    return {" ".join(unicodedata.normalize("NFKC", item).casefold().split()) for item in sentences if item.strip()}


def _assert_digest(value: dict[str, Any], field: str) -> None:
    expected = canonical_digest({key: child for key, child in value.items() if key != field})
    if value[field] != expected:
        raise ValueError(f"{field} does not match canonical content")


def _validate_gold_anchors(source_by_id: dict[str, dict[str, Any]], gold: dict[str, Any]) -> tuple[int, int]:
    entity_count = relation_count = 0
    for record in gold["records"]:
        source = source_by_id[record["caseId"]]
        text = source["rawText"]
        expected = record["expected"]
        entity_ids = set()
        occurrence_keys = set()
        entities = expected["entities"]
        for entity in entities:
            if entity["entityId"] in entity_ids or entity["occurrenceKey"] in occurrence_keys:
                raise ValueError(f"duplicate entity occurrence in {record['caseId']}")
            entity_ids.add(entity["entityId"])
            occurrence_keys.add(entity["occurrenceKey"])
            if entity["label"] != entity["evidence"]["text"]:
                raise ValueError(f"entity label/evidence mismatch in {record['caseId']}")
            _source_slice(text, entity["evidence"])
        relation_ids = set()
        for relation in expected["relations"]:
            if relation["relationId"] in relation_ids:
                raise ValueError(f"duplicate relation in {record['caseId']}")
            relation_ids.add(relation["relationId"])
            if relation["sourceEntityId"] not in entity_ids or relation["targetEntityId"] not in entity_ids:
                raise ValueError(f"relation endpoint is undeclared in {record['caseId']}")
            evidence = relation["evidence"]
            trigger = relation["triggerEvidence"]
            _source_slice(text, evidence)
            _source_slice(text, trigger)
            if not (evidence["startOffset"] <= trigger["startOffset"] and trigger["endOffset"] <= evidence["endOffset"]):
                raise ValueError(f"relation trigger is not contained in {record['caseId']}")
            endpoint_spans = {entity["entityId"]: entity["evidence"] for entity in entities}
            for endpoint_id in (relation["sourceEntityId"], relation["targetEntityId"]):
                span = endpoint_spans[endpoint_id]
                if not (evidence["startOffset"] <= span["startOffset"] and span["endOffset"] <= evidence["endOffset"]):
                    raise ValueError(f"relation endpoint span is not grounded in {record['caseId']}")
        if expected["abstentionMode"] == "none" and expected["abstentionReason"] is not None:
            raise ValueError(f"none abstention has a reason in {record['caseId']}")
        if expected["abstentionMode"] != "none" and not expected["abstentionReason"]:
            raise ValueError(f"explicit abstention lacks a reason in {record['caseId']}")
        entity_count += len(entities)
        relation_count += len(expected["relations"])
    return entity_count, relation_count


def _validate_post_evaluation_siblings(packet_dir: Path) -> None:
    """Validate immutable post-generation siblings when they are present.

    The v2 authoring packet is frozen in-place and later receives the
    candidate/evaluation artifacts.  Their presence is therefore a valid
    lifecycle phase, not a privacy failure.  The pair is still required and
    every binding is checked by the deterministic evaluator.  Unknown files
    carrying the candidate/evaluation markers remain rejected.
    """
    marker_files = {
        path.name
        for path in packet_dir.iterdir()
        if "candidate" in path.name.lower() or "evaluation" in path.name.lower()
    }
    unexpected = sorted(marker_files - POST_EVALUATION_NAMES)
    if unexpected:
        raise ValueError(f"unrecognized post-evaluation artifact(s): {unexpected}")

    candidate_path = packet_dir / CANDIDATE_NAME
    evaluation_path = packet_dir / EVALUATION_NAME
    if candidate_path.exists() != evaluation_path.exists():
        raise ValueError("post-evaluation candidate and evaluation artifacts must be present together")
    if not candidate_path.exists():
        return

    # Import lazily so the pre-candidate authoring validator remains usable
    # without loading the evaluator's larger dependency surface.
    from evaluate_s12_dense_hard_v2 import (
        validate_bindings,
        validate_evaluation_artifact,
    )

    validate_bindings(packet_dir, candidate_path)
    validate_evaluation_artifact(evaluation_path, packet_dir)

    adjudication_path = packet_dir / ADJUDICATION_NAME
    if adjudication_path.exists():
        from adjudicate_s12_dense_hard_v2_1 import validate_artifact

        validate_artifact(adjudication_path, packet_dir)


def validate_packet(packet_dir: Path = PACKET, *, require_pre_candidate: bool = False) -> dict[str, Any]:
    source = _read(packet_dir / SOURCE_NAME)
    gold = _read(packet_dir / GOLD_NAME)
    manifest = _read(packet_dir / MANIFEST_NAME)
    protocol = _read(packet_dir / PROTOCOL_NAME)
    for value, name in ((source, SOURCE_NAME), (gold, GOLD_NAME), (manifest, MANIFEST_NAME), (protocol, PROTOCOL_NAME)):
        _validate_schema(value, packet_dir / name.replace(".json", ".schema.json"))
    _assert_digest(source, "payloadDigest")
    _assert_digest(gold, "goldDigest")
    _assert_digest(manifest, "manifestDigest")
    _assert_digest(protocol, "protocolDigest")
    source_by_id = {record["caseId"]: record for record in source["records"]}
    gold_by_id = {record["caseId"]: record for record in gold["records"]}
    manifest_by_id = {record["caseId"]: record for record in manifest["records"]}
    if len(source_by_id) != 28 or set(source_by_id) != set(gold_by_id) or set(source_by_id) != set(manifest_by_id):
        raise ValueError("source, gold, and manifest must bind the same 28 unique cases")
    if source["goldIncluded"] or source["evaluatorManifestIncluded"] or source["providerCalls"] or source["heldOutInspection"]:
        raise ValueError("source-only boundary or provider flags are not clean")
    serialized_source = json.dumps(source, ensure_ascii=False)
    if any(secret in serialized_source for secret in ('"expected"', 'goldPath', 'manifestPath', 'candidateDigest')):
        raise ValueError("private evaluator material leaked into source payload")
    for record in source["records"]:
        if record["sourceDigest"] != canonical_digest({"rawText": record["rawText"]}):
            raise ValueError(f"source digest mismatch in {record['caseId']}")
    if gold["sourcePayloadDigest"] != source["payloadDigest"] or manifest["sourcePayloadDigest"] != source["payloadDigest"] or manifest["goldDigest"] != gold["goldDigest"]:
        raise ValueError("v2 cross-artifact digest binding mismatch")
    entity_count, relation_count = _validate_gold_anchors(source_by_id, gold)
    for record in manifest["records"]:
        expected = gold_by_id[record["caseId"]]["expected"]
        if record["entityCount"] != len(expected["entities"]) or record["relationCount"] != len(expected["relations"]):
            raise ValueError(f"manifest count mismatch in {record['caseId']}")
        if record["abstentionRequired"] != (record["abstentionMode"] != "none"):
            raise ValueError(f"manifest abstention mismatch in {record['caseId']}")
    v1_source = _read(V1_PACKET / "dense-hard-source-payload.v1.json")
    v1_ids = {record["caseId"] for record in v1_source["records"]}
    v1_digests = {record["sourceDigest"] for record in v1_source["records"]}
    v2_ids = set(source_by_id)
    v2_digests = {record["sourceDigest"] for record in source["records"]}
    v1_sentences = {sentence for record in v1_source["records"] for sentence in _sentence_set(record["rawText"])}
    v2_sentences = {sentence for record in source["records"] for sentence in _sentence_set(record["rawText"])}
    no_reuse = {"caseIdsDisjoint": not v1_ids & v2_ids, "sourceDigestsDisjoint": not v1_digests & v2_digests, "normalizedSentencesDisjoint": not v1_sentences & v2_sentences, "sourcePayloadDigestFresh": source["payloadDigest"] != v1_source["payloadDigest"], "rawTextChanged": all(record["rawText"] not in {old["rawText"] for old in v1_source["records"]} for record in source["records"])}
    if not all(no_reuse.values()):
        raise ValueError(f"v1 reuse detected: {no_reuse}")
    if require_pre_candidate and any(
        "candidate" in path.name.lower() or "evaluation" in path.name.lower()
        for path in packet_dir.iterdir()
    ):
        raise ValueError("pre-candidate packet contains candidate/evaluation artifact")
    if not require_pre_candidate:
        _validate_post_evaluation_siblings(packet_dir)
    result = {"artifactVersion": "s12.dense-hard.v2-lineage.v1", "status": "VALIDATED_FRESH_NO_V1_REUSE", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "sourcePayloadDigest": source["payloadDigest"], "goldDigest": gold["goldDigest"], "manifestDigest": manifest["manifestDigest"], "protocolDigest": protocol["protocolDigest"], "v1SourcePayloadDigest": v1_source["payloadDigest"], "caseCount": len(source["records"]), "entityAssertions": entity_count, "relationAssertions": relation_count, "sliceCount": len({item for record in source["records"] for item in record["slices"]}), "abstentionCaseCount": manifest["abstentionCaseCount"], "fullAbstentionCaseCount": sum(record["abstentionMode"] == "full" for record in manifest["records"]), "partialAbstentionCaseCount": sum(record["abstentionMode"] == "partial" for record in manifest["records"]), "noReuseChecks": no_reuse, "authorIneligibleForCandidate": True, "providerCalls": 0, "nonClaims": ["No v2 candidate, score, review, provider, human, external, held-out, production, selection, promotion, or release result is present."]}
    result["lineageDigest"] = canonical_digest(result)
    return result


def validate_candidate_response(response: dict[str, Any], source_record: dict[str, Any], supported_assertion_ids: set[str] | None = None, protocol: dict[str, Any] | None = None) -> None:
    """Validate a proposed response without writing or scoring a candidate."""
    protocol = protocol or _read(PACKET / PROTOCOL_NAME)
    allowed = {"protocolVersion", "entities", "relations", "abstention", "quarantinedAssertions"}
    if set(response) != allowed or response["protocolVersion"] != "dense-hard-output.v2":
        raise ProtocolGuardError("response envelope does not match the v2 source-only protocol")
    text = source_record["rawText"]
    types = set(protocol["finiteEntityTypes"])
    predicates = set(protocol["finiteRelationPredicates"])
    entity_ids: set[str] = set()
    occurrence_keys: set[str] = set()
    spans: dict[str, dict[str, int]] = {}
    for item in response["entities"]:
        if set(item) != {"entityId", "occurrenceKey", "type", "label", "evidence"} or item["entityId"] in entity_ids or item["occurrenceKey"] in occurrence_keys:
            raise ProtocolGuardError("entity identity or occurrence registry violation")
        if item["type"] not in types or item["label"] != item["evidence"]["text"]:
            raise ProtocolGuardError("entity type policy or label grounding violation")
        _source_slice(text, item["evidence"])
        entity_ids.add(item["entityId"])
        occurrence_keys.add(item["occurrenceKey"])
        spans[item["entityId"]] = item["evidence"]
        if supported_assertion_ids is not None and item["entityId"] not in supported_assertion_ids:
            raise ProtocolGuardError("unsupported finalized entity must be quarantined")
    relation_ids: set[str] = set()
    for item in response["relations"]:
        required = {"relationId", "predicate", "sourceEntityId", "targetEntityId", "triggerEvidence", "evidence"}
        if set(item) != required or item["relationId"] in relation_ids or item["predicate"] not in predicates:
            raise ProtocolGuardError("relation identity or predicate policy violation")
        if item["sourceEntityId"] not in entity_ids or item["targetEntityId"] not in entity_ids:
            raise ProtocolGuardError("relation endpoint is not a declared occurrence")
        evidence, trigger = item["evidence"], item["triggerEvidence"]
        _source_slice(text, evidence)
        _source_slice(text, trigger)
        if not (evidence["startOffset"] <= trigger["startOffset"] and trigger["endOffset"] <= evidence["endOffset"]):
            raise ProtocolGuardError("relation trigger is not grounded inside relation evidence")
        for endpoint in (spans[item["sourceEntityId"]], spans[item["targetEntityId"]]):
            if not (evidence["startOffset"] <= endpoint["startOffset"] and endpoint["endOffset"] <= evidence["endOffset"]):
                raise ProtocolGuardError("relation endpoint span is not contained by relation evidence")
        if supported_assertion_ids is not None and item["relationId"] not in supported_assertion_ids:
            raise ProtocolGuardError("unsupported finalized relation must be quarantined")
        relation_ids.add(item["relationId"])
    quarantined = response["quarantinedAssertions"]
    quarantined_ids: set[str] = set()
    for item in quarantined:
        if set(item) != {"assertionId", "kind", "reasonCode", "status"} or item["status"] != "quarantined" or item["kind"] not in {"entity", "relation"} or not item["reasonCode"] or item["assertionId"] in quarantined_ids or item["assertionId"] in entity_ids or item["assertionId"] in relation_ids:
            raise ProtocolGuardError("quarantine record is invalid or finalized")
        quarantined_ids.add(item["assertionId"])
    abstention = response["abstention"]
    if set(abstention) != {"mode", "reasonCode"} or abstention["mode"] not in {"none", "partial", "full"}:
        raise ProtocolGuardError("abstention envelope is invalid")
    mode = abstention["mode"]
    if mode == "none" and (abstention["reasonCode"] is not None or quarantined):
        raise ProtocolGuardError("none mode cannot hide quarantined assertions")
    if mode == "partial" and (not entity_ids and not relation_ids or not quarantined):
        raise ProtocolGuardError("partial mode requires finalized and quarantined propositions")
    if mode == "full" and (entity_ids or relation_ids or not quarantined):
        raise ProtocolGuardError("full mode requires no finalized assertions and at least one quarantine")
    if mode != "none" and not abstention["reasonCode"]:
        raise ProtocolGuardError("explicit abstention requires a reason")


def write_lineage(packet_dir: Path = PACKET) -> Path:
    value = validate_packet(packet_dir)
    path = packet_dir / LINEAGE_NAME
    schema_path = packet_dir / "dense-hard-v2-lineage.v1.schema.json"
    _validate_schema(value, schema_path)
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable lineage artifact differs: {path}")
    if not path.exists():
        path.write_text(content, encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pre-candidate",
        action="store_true",
        help="require the packet to be frozen before candidate/evaluation generation",
    )
    args = parser.parse_args()
    print(json.dumps(validate_packet(require_pre_candidate=args.pre_candidate), ensure_ascii=False, sort_keys=True))
