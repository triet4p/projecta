"""Focused fail-closed and freshness tests for the v3 authoring packet."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from generate_s12_dense_hard_v3 import PACKET, SLICES
from jsonschema import Draft202012Validator
from validate_s12_dense_hard_v3 import validate_packet


def test_v3_packet_and_lineage_are_valid() -> None:
    result = validate_packet()
    assert result["caseCount"] == 30
    assert result["sliceCount"] >= 21
    assert result["entityAssertions"] == 104
    assert result["relationAssertions"] == 44
    assert result["fullAbstentionCaseCount"] >= 1
    assert result["partialAbstentionCaseCount"] >= 1
    assert all(result["noReuseChecks"].values())


def test_all_strict_draft_2020_12_schemas_validate_artifacts() -> None:
    for schema_path in PACKET.glob("*.schema.json"):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        artifact_path = PACKET / schema_path.name.removesuffix(".schema.json")
        if artifact_path.exists():
            value = json.loads(artifact_path.read_text(encoding="utf-8"))
            errors = list(Draft202012Validator(schema).iter_errors(value))
            assert not errors, f"{schema_path.name}: {errors[0].message if errors else ''}"


def test_protocol_exposes_corrected_identity_rubric_and_matrix() -> None:
    protocol = json.loads((PACKET / "dense-hard-source-only-protocol.v3.json").read_text(encoding="utf-8"))
    contract = json.loads((PACKET / "dense-hard-evaluator-contract.v3.json").read_text(encoding="utf-8"))
    assert set(protocol["finiteEntityTypes"]) == set(protocol["typeRubric"]["rules"])
    assert protocol["propositionRegistry"]["occurrenceIdentity"] == ["startOffset", "endOffset", "text"]
    assert protocol["relationGrounding"]["typeMismatchDoesNotCascade"] is True
    assert protocol["abstentionMatrix"]["typeUncertainty"]
    assert contract["status"] == "CONTRACT_BEFORE_CANDIDATE"
    assert contract["noCandidateOrEvaluation"] is True


def test_packet_has_all_22_registered_slices_and_source_stays_private() -> None:
    source = json.loads((PACKET / "dense-hard-source-payload.v3.json").read_text(encoding="utf-8"))
    found = {item for record in source["records"] for item in record["slices"]}
    assert found == set(SLICES)
    assert source["goldIncluded"] is False
    assert source["evaluatorManifestIncluded"] is False
    assert source["heldOutInspection"] is False


def test_source_mutation_fails_closed(tmp_path: Path) -> None:
    for path in PACKET.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())
    source_path = tmp_path / "dense-hard-source-payload.v3.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["records"][0]["rawText"] += " tampered"
    source_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="payloadDigest|source digest"):
        validate_packet(tmp_path)


def test_protocol_mutation_fails_closed(tmp_path: Path) -> None:
    for path in PACKET.iterdir():
        if path.is_file():
            (tmp_path / path.name).write_bytes(path.read_bytes())
    protocol_path = tmp_path / "dense-hard-source-only-protocol.v3.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol["relationGrounding"]["typeMismatchDoesNotCascade"] = False
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    with pytest.raises(ValueError, match="protocolDigest|typeMismatch|cascade"):
        validate_packet(tmp_path)
