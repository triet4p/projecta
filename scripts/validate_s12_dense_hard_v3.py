"""Fail-closed validation for the fresh dense-hard v3 authoring packet."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v3"
V1 = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v1/dense-hard-source-payload.v1.json"
V2 = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v2/dense-hard-source-payload.v2.json"
SHA = re.compile(r"^sha256:[0-9a-f]{64}$")


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(value: dict[str, Any], path: Path) -> None:
    schema = read(path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: list(e.path))
    if errors:
        raise ValueError(f"{path.name}: {list(errors[0].path)}: {errors[0].message}")


def exact(text: str, item: dict[str, Any]) -> None:
    start, end = item["startOffset"], item["endOffset"]
    if start < 0 or end <= start or end > len(text) or text[start:end] != item["text"]:
        raise ValueError("invalid Unicode half-open evidence anchor")


def sentence_set(text: str) -> set[str]:
    parts = re.split(r"[.!?。！？]+", text)
    return {" ".join(unicodedata.normalize("NFKC", p).casefold().split()) for p in parts if p.strip()}


def validate_packet(packet_dir: Path = PACKET) -> dict[str, Any]:
    names = {
        "source": "dense-hard-source-payload.v3.json", "gold": "dense-hard-gold.v3.json", "manifest": "dense-hard-evaluator-manifest.v3.json",
        "protocol": "dense-hard-source-only-protocol.v3.json", "contract": "dense-hard-evaluator-contract.v3.json",
    }
    values = {key: read(packet_dir / name) for key, name in names.items()}
    for key, name in names.items():
        validate_schema(values[key], packet_dir / name.replace(".json", ".schema.json"))
    for key, field in (("source", "payloadDigest"), ("gold", "goldDigest"), ("manifest", "manifestDigest"), ("protocol", "protocolDigest"), ("contract", "contractDigest")):
        if values[key][field] != digest({k: v for k, v in values[key].items() if k != field}):
            raise ValueError(f"{field} mismatch")
    source, gold, manifest, protocol, contract = (values[key] for key in ("source", "gold", "manifest", "protocol", "contract"))
    if len(source["records"]) != 30 or len(gold["records"]) != 30 or len(manifest["records"]) != 30:
        raise ValueError("v3 requires exactly 30 cases")
    source_by_id = {r["caseId"]: r for r in source["records"]}
    gold_by_id = {r["caseId"]: r for r in gold["records"]}
    manifest_by_id = {r["caseId"]: r for r in manifest["records"]}
    if len(source_by_id) != 30 or set(source_by_id) != set(gold_by_id) or set(source_by_id) != set(manifest_by_id):
        raise ValueError("source/gold/manifest case bindings are not one-to-one")
    if not source["sourceOnly"] or source["goldIncluded"] or source["evaluatorManifestIncluded"] or source["providerCalls"] or source["heldOutInspection"]:
        raise ValueError("source-only boundary is not clean")
    leaked = json.dumps(source, ensure_ascii=False).lower()
    if any(term in leaked for term in ("\"expected\"", "goldpath", "manifestpath", "candidatedigest", "candidatepath")):
        raise ValueError("private evaluator material leaked into source")
    if gold["sourcePayloadDigest"] != source["payloadDigest"] or manifest["sourcePayloadDigest"] != source["payloadDigest"] or manifest["goldDigest"] != gold["goldDigest"]:
        raise ValueError("cross-artifact digest binding mismatch")
    if set(protocol["finiteEntityTypes"]) != set(protocol["typeRubric"]["rules"]) or len(protocol["finiteEntityTypes"]) != len(protocol["typeRubric"]["rules"]):
        raise ValueError("finite type list must bind the public rubric")
    if not protocol["propositionRegistry"]["identityIndependentOfType"] or not protocol["relationGrounding"]["typeMismatchDoesNotCascade"]:
        raise ValueError("v3 identity/cascade correction missing")
    if contract["status"] != "CONTRACT_BEFORE_CANDIDATE" or not contract["noCandidateOrEvaluation"]:
        raise ValueError("contract status is not pre-candidate")
    entity_count = relation_count = 0
    for case_id, record in source_by_id.items():
        if record["sourceDigest"] != digest({"rawText": record["rawText"]}):
            raise ValueError(f"source digest mismatch in {case_id}")
        expected = gold_by_id[case_id]["expected"]
        entities = expected["entities"]
        entity_ids = {e["entityId"] for e in entities}
        occurrence_keys = {e["occurrenceKey"] for e in entities}
        if len(entity_ids) != len(entities) or len(occurrence_keys) != len(entities):
            raise ValueError(f"duplicate occurrence identity in {case_id}")
        for e in entities:
            if e["label"] != e["evidence"]["text"] or e["type"] not in protocol["finiteEntityTypes"]:
                raise ValueError(f"entity rubric/label violation in {case_id}")
            exact(record["rawText"], e["evidence"])
        for rel in expected["relations"]:
            if rel["sourceEntityId"] not in entity_ids or rel["targetEntityId"] not in entity_ids:
                raise ValueError(f"undeclared relation endpoint in {case_id}")
            exact(record["rawText"], rel["evidence"])
            exact(record["rawText"], rel["triggerEvidence"])
            if not (rel["evidence"]["startOffset"] <= rel["triggerEvidence"]["startOffset"] < rel["triggerEvidence"]["endOffset"] <= rel["evidence"]["endOffset"]):
                raise ValueError(f"trigger boundary violation in {case_id}")
            endpoint_by_id = {e["entityId"]: e["evidence"] for e in entities}
            for endpoint_id in (rel["sourceEntityId"], rel["targetEntityId"]):
                endpoint = endpoint_by_id[endpoint_id]
                if not (rel["evidence"]["startOffset"] <= endpoint["startOffset"] and endpoint["endOffset"] <= rel["evidence"]["endOffset"]):
                    raise ValueError(f"endpoint grounding violation in {case_id}")
        mode = expected["abstentionMode"]
        if mode == "none" and (expected["abstentionReason"] is not None or expected["quarantineCount"] != 0):
            raise ValueError(f"none mode hides unsafe content in {case_id}")
        if mode == "full" and (entities or expected["relations"]):
            raise ValueError(f"full abstention contains safe finalizations in {case_id}")
        if mode != "none" and (not expected["abstentionReason"] or expected["quarantineCount"] < 1):
            raise ValueError(f"abstention matrix violation in {case_id}")
        m = manifest_by_id[case_id]
        if (m["entityCount"], m["relationCount"], m["abstentionMode"], m["quarantineCount"]) != (len(entities), len(expected["relations"]), mode, expected["quarantineCount"]):
            raise ValueError(f"manifest mismatch in {case_id}")
        entity_count += len(entities)
        relation_count += len(expected["relations"])
    slices = {item for record in source["records"] for item in record["slices"]}
    if len(slices) < 21:
        raise ValueError("fewer than 21 slices")
    if not any(r["expected"]["abstentionMode"] == "full" for r in gold["records"]) or not any(r["expected"]["abstentionMode"] == "partial" for r in gold["records"]):
        raise ValueError("normal/full/partial abstention coverage missing")
    old = [read(V1), read(V2)]
    ids = {r["caseId"] for r in source["records"]}
    digests = {r["sourceDigest"] for r in source["records"]}
    raw = {r["rawText"] for r in source["records"]}
    no_reuse: dict[str, bool] = {}
    for version, prior in zip(("V1", "V2"), old, strict=True):
        prior_ids = {r["caseId"] for r in prior["records"]}
        prior_digests = {r["sourceDigest"] for r in prior["records"]}
        prior_raw = {r["rawText"] for r in prior["records"]}
        prior_sentences = {s for r in prior["records"] for s in sentence_set(r["rawText"])}
        new_sentences = {s for r in source["records"] for s in sentence_set(r["rawText"])}
        no_reuse.update({f"caseIdsDisjoint{version}": not ids & prior_ids, f"sourceDigestsDisjoint{version}": not digests & prior_digests, f"normalizedSentencesDisjoint{version}": not new_sentences & prior_sentences, f"sourcePayloadDigestFresh{version}": source["payloadDigest"] != prior["payloadDigest"], f"rawTextChanged{version}": not raw & prior_raw})
    if not all(no_reuse.values()):
        raise ValueError(f"v1/v2 reuse detected: {no_reuse}")
    result: dict[str, Any] = {"artifactVersion": "s12.dense-hard.v3-lineage.v1", "status": "VALIDATED_FRESH_NO_V1_V2_REUSE", "datasetKind": "SYNTHETIC_NON_PRODUCTION", "sourcePayloadDigest": source["payloadDigest"], "goldDigest": gold["goldDigest"], "manifestDigest": manifest["manifestDigest"], "protocolDigest": protocol["protocolDigest"], "contractDigest": contract["contractDigest"], "v1SourcePayloadDigest": old[0]["payloadDigest"], "v2SourcePayloadDigest": old[1]["payloadDigest"], "caseCount": 30, "entityAssertions": entity_count, "relationAssertions": relation_count, "sliceCount": len(slices), "abstentionCaseCount": manifest["abstentionCaseCount"], "fullAbstentionCaseCount": sum(r["abstentionMode"] == "full" for r in manifest["records"]), "partialAbstentionCaseCount": sum(r["abstentionMode"] == "partial" for r in manifest["records"]), "noReuseChecks": no_reuse, "authorIneligibleForCandidate": True, "providerCalls": 0, "nonClaims": ["No v3 candidate, evaluation, review, provider, human, external, held-out, production, selection, promotion, or release result is present."]}
    result["lineageDigest"] = digest(result)
    return result


def write_lineage(packet_dir: Path = PACKET) -> dict[str, Any]:
    value = validate_packet(packet_dir)
    validate_schema(value, packet_dir / "dense-hard-v3-lineage.v1.schema.json")
    path = packet_dir / "dense-hard-v3-lineage.v1.json"
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError(f"immutable lineage differs: {path}")
    path.write_text(content, encoding="utf-8")
    return value


if __name__ == "__main__":
    print(json.dumps(write_lineage(), ensure_ascii=False, sort_keys=True))
