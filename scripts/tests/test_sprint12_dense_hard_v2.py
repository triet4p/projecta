"""Contract and fail-closed tests for the fresh dense-hard v2 author packet."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from validate_s12_dense_hard_v2 import (
    PACKET,
    ProtocolGuardError,
    validate_candidate_response,
    validate_packet,
    write_lineage,
)


def _read(name: str) -> dict:
    return json.loads((PACKET / name).read_text(encoding="utf-8"))


def test_v2_packet_is_strict_fresh_and_private_gold_is_separate() -> None:
    result = validate_packet()
    assert result["caseCount"] == 28
    assert result["entityAssertions"] == 113
    assert result["relationAssertions"] == 49
    assert result["sliceCount"] == 21
    assert result["abstentionCaseCount"] == 10
    assert result["fullAbstentionCaseCount"] == 6
    assert result["partialAbstentionCaseCount"] == 4
    assert all(result["noReuseChecks"].values())
    for name in (
        "dense-hard-source-payload.v2.json",
        "dense-hard-gold.v2.json",
        "dense-hard-evaluator-manifest.v2.json",
        "dense-hard-source-only-protocol.v2.json",
        "dense-hard-v2-lineage.v1.json",
    ):
        value = _read(name)
        schema = _read(name.replace(".json", ".schema.json"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    source_text = (PACKET / "dense-hard-source-payload.v2.json").read_text(encoding="utf-8")
    assert '"expected"' not in source_text
    assert '"goldPath"' not in source_text
    assert '"manifestPath"' not in source_text
    assert not list(PACKET.glob("*review*"))


def test_v2_post_evaluation_lifecycle_validates_immutable_siblings() -> None:
    # The frozen candidate/evaluation are valid post-generation siblings.  The
    # default validator checks their schemas, digests, and cross-artifact
    # bindings instead of treating their filenames as a permanent violation.
    assert validate_packet()["caseCount"] == 28


def test_v2_pre_candidate_lifecycle_rejects_post_evaluation_siblings() -> None:
    with pytest.raises(ValueError, match="pre-candidate packet contains"):
        validate_packet(require_pre_candidate=True)


def test_v2_pre_candidate_lifecycle_accepts_clean_authoring_packet(tmp_path: Path) -> None:
    authoring_names = (
        "dense-hard-source-payload.v2.json",
        "dense-hard-source-payload.v2.schema.json",
        "dense-hard-gold.v2.json",
        "dense-hard-gold.v2.schema.json",
        "dense-hard-evaluator-manifest.v2.json",
        "dense-hard-evaluator-manifest.v2.schema.json",
        "dense-hard-source-only-protocol.v2.json",
        "dense-hard-source-only-protocol.v2.schema.json",
    )
    clean = tmp_path / "dense-hard-v2"
    clean.mkdir()
    for name in authoring_names:
        shutil.copy2(PACKET / name, clean / name)
    assert validate_packet(clean, require_pre_candidate=True)["caseCount"] == 28


def test_v2_gold_anchors_and_occurrence_registry_are_exact() -> None:
    source = {record["caseId"]: record for record in _read("dense-hard-source-payload.v2.json")["records"]}
    gold = _read("dense-hard-gold.v2.json")
    for record in gold["records"]:
        text = source[record["caseId"]]["rawText"]
        occurrence_keys = [item["occurrenceKey"] for item in record["expected"]["entities"]]
        assert len(occurrence_keys) == len(set(occurrence_keys))
        for item in record["expected"]["entities"]:
            evidence = item["evidence"]
            assert text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"]
        for item in record["expected"]["relations"]:
            for evidence in (item["triggerEvidence"], item["evidence"]):
                assert text[evidence["startOffset"] : evidence["endOffset"]] == evidence["text"]
            assert item["triggerEvidence"]["text"] in item["evidence"]["text"]
    assert any("combining-mark" in item["slices"] for item in _read("dense-hard-evaluator-manifest.v2.json")["records"])
    assert any("emoji" in item["slices"] for item in _read("dense-hard-evaluator-manifest.v2.json")["records"])


def test_generic_guard_accepts_grounded_response_without_scoring() -> None:
    source = _read("dense-hard-source-payload.v2.json")["records"][0]
    expected = _read("dense-hard-gold.v2.json")["records"][0]["expected"]
    response = {"protocolVersion": "dense-hard-output.v2", "entities": expected["entities"], "relations": expected["relations"], "abstention": {"mode": "none", "reasonCode": None}, "quarantinedAssertions": []}
    validate_candidate_response(response, source, {item["entityId"] for item in expected["entities"]} | {item["relationId"] for item in expected["relations"]})


def test_generic_guard_quarantines_unsupported_assertion() -> None:
    source = _read("dense-hard-source-payload.v2.json")["records"][8]
    expected = _read("dense-hard-gold.v2.json")["records"][8]["expected"]
    response = {"protocolVersion": "dense-hard-output.v2", "entities": expected["entities"], "relations": [], "abstention": {"mode": "partial", "reasonCode": "AMBIGUOUS_RELATION_SCOPE"}, "quarantinedAssertions": [{"assertionId": "proposed-relation-1", "kind": "relation", "reasonCode": "AMBIGUOUS_RELATION_SCOPE", "status": "quarantined"}]}
    supported = {item["entityId"] for item in expected["entities"]}
    validate_candidate_response(response, source, supported)
    response["entities"] = [*response["entities"], {"entityId": "unsupported-entity", "occurrenceKey": "unsupported-occurrence", "type": "Requirement", "label": "Amber docket", "evidence": expected["entities"][0]["evidence"]}]
    with pytest.raises(ProtocolGuardError, match="unsupported finalized entity"):
        validate_candidate_response(response, source, supported)


@pytest.mark.parametrize("mutation", ["source_digest", "gold_anchor", "manifest_count", "protocol_digest"])
def test_v2_packet_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    target = tmp_path / "dense-hard-v2"
    shutil.copytree(PACKET, target)
    if mutation == "source_digest":
        path = target / "dense-hard-source-payload.v2.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["payloadDigest"] = "sha256:" + "0" * 64
    elif mutation == "gold_anchor":
        path = target / "dense-hard-gold.v2.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["records"][0]["expected"]["entities"][0]["evidence"]["text"] = "tampered"
    elif mutation == "manifest_count":
        path = target / "dense-hard-evaluator-manifest.v2.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["records"][0]["entityCount"] += 1
    else:
        path = target / "dense-hard-source-only-protocol.v2.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["protocolDigest"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_packet(target)


def test_lineage_writer_is_immutable() -> None:
    assert write_lineage() == PACKET / "dense-hard-v2-lineage.v1.json"
