"""Strict source/gold/manifest validator for the dense-hard benchmark packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "evaluation/sprint-12/internal-poc/dense-hard-v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stable(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_stable(value)).hexdigest()


def _validate_schema(value: dict[str, Any], schema_path: Path) -> None:
    schema = _load(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ValueError(f"{schema_path.name}: {errors[0].message}")


def _anchor(text: str, evidence: dict[str, Any]) -> None:
    start, end = evidence["startOffset"], evidence["endOffset"]
    if start < 0 or end <= start or end > len(text) or text[start:end] != evidence["text"]:
        raise ValueError("invalid Unicode code-point evidence anchor")


def _private_keys(value: object) -> list[str]:
    """Return evaluator-only fields accidentally embedded in source data."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"expected", "goldPath", "goldDigest"}:
                found.append(key)
            found.extend(_private_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_private_keys(child))
    return found


def validate_packets(packet_dir: Path = PACKET) -> dict[str, Any]:
    source_path = packet_dir / "dense-hard-source-payload.v1.json"
    gold_path = packet_dir / "dense-hard-gold.v1.json"
    manifest_path = packet_dir / "dense-hard-evaluator-manifest.v1.json"
    source = _load(source_path)
    gold = _load(gold_path)
    manifest = _load(manifest_path)
    _validate_schema(source, packet_dir / "dense-hard-source-payload.v1.schema.json")
    _validate_schema(gold, packet_dir / "dense-hard-gold.v1.schema.json")
    _validate_schema(manifest, packet_dir / "dense-hard-evaluator-manifest.v1.schema.json")
    if source["payloadDigest"] != _digest({key: value for key, value in source.items() if key != "payloadDigest"}):
        raise ValueError("source payload digest mismatch")
    if gold["goldDigest"] != _digest({key: value for key, value in gold.items() if key != "goldDigest"}):
        raise ValueError("gold digest mismatch")
    if manifest["manifestDigest"] != _digest({key: value for key, value in manifest.items() if key != "manifestDigest"}):
        raise ValueError("evaluator manifest digest mismatch")
    if gold["sourcePayloadDigest"] != source["payloadDigest"] or manifest["sourcePayloadDigest"] != source["payloadDigest"] or manifest["goldDigest"] != gold["goldDigest"]:
        raise ValueError("cross-artifact digest binding mismatch")
    if _private_keys(source):
        raise ValueError("source-only payload contains private evaluator material")
    source_by_id = {record["caseId"]: record for record in source["records"]}
    gold_by_id = {record["caseId"]: record for record in gold["records"]}
    manifest_by_id = {record["caseId"]: record for record in manifest["records"]}
    if set(source_by_id) != set(gold_by_id) or set(source_by_id) != set(manifest_by_id):
        raise ValueError("case ID sets are not identical")
    for case_id, source_record in source_by_id.items():
        gold_record = gold_by_id[case_id]
        manifest_record = manifest_by_id[case_id]
        if source_record["sourceDigest"] != gold_record["sourceDigest"]:
            raise ValueError(f"source digest mismatch for {case_id}")
        if source_record["sourceDigest"] != "sha256:" + hashlib.sha256(source_record["rawText"].encode("utf-8")).hexdigest():
            raise ValueError(f"raw source digest mismatch for {case_id}")
        expected = gold_record["expected"]
        entity_ids = {entity["entityId"] for entity in expected["entities"]}
        for entity in expected["entities"]:
            _anchor(source_record["rawText"], entity["evidence"])
        for relation in expected["relations"]:
            _anchor(source_record["rawText"], relation["evidence"])
            if relation["sourceEntityId"] not in entity_ids or relation["targetEntityId"] not in entity_ids:
                raise ValueError(f"dangling gold relation for {case_id}")
            if relation["sourceEntityId"] == relation["targetEntityId"]:
                raise ValueError(f"self relation for {case_id}")
        if manifest_record["entityCount"] != len(expected["entities"] or []) or manifest_record["relationCount"] != len(expected["relations"] or []):
            raise ValueError(f"manifest count mismatch for {case_id}")
    return {"status": "PACKET_VALID", "caseCount": len(source_by_id), "entityAssertions": sum(len(record["expected"]["entities"]) for record in gold["records"]), "relationAssertions": sum(len(record["expected"]["relations"]) for record in gold["records"]), "abstentionCases": sum(record["expected"]["abstentionReason"] is not None for record in gold["records"]), "sourcePayloadDigest": source["payloadDigest"], "goldDigest": gold["goldDigest"], "manifestDigest": manifest["manifestDigest"]}


if __name__ == "__main__":
    print(json.dumps(validate_packets(), sort_keys=True))
