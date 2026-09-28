"""Contract tests for the source-only dense-hard benchmark packet."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from evaluate_s12_dense_hard_v1 import evaluate
from jsonschema import Draft202012Validator, ValidationError
from validate_s12_dense_hard_v1 import PACKET, validate_packets


def _read(name: str) -> dict:
    return json.loads((PACKET / name).read_text(encoding="utf-8"))


def _copy_packet(tmp_path: Path) -> Path:
    target = tmp_path / "dense-hard-v1"
    shutil.copytree(PACKET, target)
    return target


def test_packet_schemas_digests_and_complexity() -> None:
    source = _read("dense-hard-source-payload.v1.json")
    gold = _read("dense-hard-gold.v1.json")
    manifest = _read("dense-hard-evaluator-manifest.v1.json")
    for packet, schema_name in (
        (source, "dense-hard-source-payload.v1.schema.json"),
        (gold, "dense-hard-gold.v1.schema.json"),
        (manifest, "dense-hard-evaluator-manifest.v1.schema.json"),
    ):
        schema = _read(schema_name)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(packet)
    result = validate_packets()
    assert result["caseCount"] == 24
    assert result["entityAssertions"] == 101
    assert result["relationAssertions"] == 49
    assert result["abstentionCases"] == 11
    assert source["goldIncluded"] is False
    assert source["evaluatorManifestIncluded"] is False
    for source_record, manifest_record, gold_record in zip(
        source["records"], manifest["records"], gold["records"], strict=True
    ):
        sentence_count = source_record["rawText"].count(".") + source_record["rawText"].count("。")
        assert 2 <= sentence_count <= 5
        if not manifest_record["abstentionRequired"]:
            assert 4 <= manifest_record["entityCount"] <= 10
            assert 3 <= manifest_record["relationCount"] <= 8
        assert manifest_record["entityCount"] == len(gold_record["expected"]["entities"])


def test_source_payload_contains_no_private_gold_material() -> None:
    source_text = (PACKET / "dense-hard-source-payload.v1.json").read_text(encoding="utf-8")
    assert '"expected"' not in source_text
    assert '"goldPath"' not in source_text
    assert "PRIVATE_FOR_EVALUATOR_ONLY" not in source_text
    assert "rawText" in source_text
    assert (PACKET / "dense-hard-gold.v1.json") != (PACKET / "dense-hard-source-payload.v1.json")


def test_gold_anchors_are_exact_and_repeated_occurrences_are_bound() -> None:
    source = {record["caseId"]: record for record in _read("dense-hard-source-payload.v1.json")["records"]}
    gold = _read("dense-hard-gold.v1.json")
    for record in gold["records"]:
        text = source[record["caseId"]]["rawText"]
        for entity in record["expected"]["entities"]:
            evidence = entity["evidence"]
            assert text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"]
        for relation in record["expected"]["relations"]:
            evidence = relation["evidence"]
            assert text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"]
    repeated = source["dh-005"]["rawText"]
    labels = [
        entity["evidence"]["text"]
        for entity in next(r for r in gold["records"] if r["caseId"] == "dh-005")["expected"]["entities"]
    ]
    assert sum(label.lower() == "review queue" for label in labels) == 2
    lowered = repeated.lower()
    assert lowered.find("review queue") != lowered.rfind("review queue")


@pytest.mark.parametrize(
    "mutation",
    ["source_digest", "private_field", "gold_evidence", "manifest_count"],
)
def test_packet_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    packet = _copy_packet(tmp_path)
    if mutation == "source_digest":
        path = packet / "dense-hard-source-payload.v1.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["payloadDigest"] = "sha256:" + "0" * 64
        path.write_text(json.dumps(value), encoding="utf-8")
    elif mutation == "private_field":
        path = packet / "dense-hard-source-payload.v1.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["records"][0]["expected"] = {}
        path.write_text(json.dumps(value), encoding="utf-8")
    elif mutation == "gold_evidence":
        path = packet / "dense-hard-gold.v1.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["records"][0]["expected"]["entities"][0]["evidence"]["text"] = "tampered"
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        path = packet / "dense-hard-evaluator-manifest.v1.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["records"][0]["relationCount"] += 1
        path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises((ValueError, ValidationError)):
        validate_packets(packet)


def test_evaluator_does_not_score_without_candidate() -> None:
    result = evaluate()
    assert result["status"] == "CANDIDATE_NOT_PROVIDED"
    assert result["scoreProduced"] is False
