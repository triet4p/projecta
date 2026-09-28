"""Fail-closed tests for the separate protocol-fair v2.1 adjudication."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from adjudicate_s12_dense_hard_v2_1 import PACKET, validate_artifact, write_immutable
from jsonschema import Draft202012Validator


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_packet(tmp_path: Path) -> Path:
    target = tmp_path / "dense-hard-v2"
    shutil.copytree(PACKET, target)
    return target


def test_adjudication_is_strict_deterministic_and_preserves_legacy_view() -> None:
    value = validate_artifact()
    schema = _read(PACKET / "dense-hard-evaluation-adjudication.v2.1.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    fair = value["protocolFair"]
    assert value["candidateDigest"] == "sha256:568f2ff212307b7f88c02706e297fd6567582b8ef498eb7c88f475363a37784d"
    assert value["originalEvaluationDigest"] == "sha256:54e607e50e54b39c4934ead017878d6a2ba18cc89254db4872f247933e99eb71"
    original = _read(PACKET / "dense-hard-evaluation.v2.json")
    assert value["legacyStrict"]["evaluationDigest"] == original["evaluationDigest"]
    assert value["legacyStrict"]["perItemClassificationCounts"] == original["perItemClassificationCounts"]
    assert fair["typeDimension"] == {"corrections": 36, "excludedFromPassFail": True, "status": "UNSCORABLE_PROTOCOL_AMBIGUITY"}
    assert fair["perItemClassificationCounts"] == {"unchanged": 0, "minor": 12, "major": 0, "reject": 0, "abstain": 16}
    assert fair["semanticEditCounts"] == {"total": 14, "meanPerCase": 0.5}
    assert fair["entityMetrics"]["f1"] == 0.968609865470852
    assert fair["relationMetrics"]["f1"] == 0.923076923076923
    assert fair["quarantineMetrics"]["precision"] == 1.0
    assert fair["quarantineMetrics"]["recall"] == 21 / 23
    assert fair["unsafeFinalizedAssertionsAvoided"]["unsafeFinalized"] == 2
    assert fair["rm67"]["editBurdenGate"] is False
    assert value["v1Comparison"]["pooled"] is False


def test_audit_examples_show_type_cascade_removed() -> None:
    examples = validate_artifact()["auditExamples"]
    assert examples["dh2-001"]["deltas"] == {"semanticEditCount": -12, "unsupportedFinalizedAssertions": -9, "hallucinatedFinalizedAssertions": -3, "typeCorrectionsExcluded": 6}
    assert examples["dh2-002"]["deltas"] == {"semanticEditCount": -10, "unsupportedFinalizedAssertions": -7, "hallucinatedFinalizedAssertions": -3, "typeCorrectionsExcluded": 4}
    assert examples["dh2-006"]["deltas"] == {"semanticEditCount": -9, "unsupportedFinalizedAssertions": -6, "hallucinatedFinalizedAssertions": -3, "typeCorrectionsExcluded": 3}
    assert examples["dh2-017"]["deltas"] == {"semanticEditCount": -8, "unsupportedFinalizedAssertions": -6, "hallucinatedFinalizedAssertions": -2, "typeCorrectionsExcluded": 4}
    assert examples["dh2-022"]["deltas"] == {"semanticEditCount": -11, "unsupportedFinalizedAssertions": -8, "hallucinatedFinalizedAssertions": -3, "typeCorrectionsExcluded": 5}


def test_adjudication_writer_is_immutable() -> None:
    assert write_immutable() == PACKET / "dense-hard-evaluation-adjudication.v2.1.json"


def test_adjudication_mutation_fails_closed(tmp_path: Path) -> None:
    packet = _copy_packet(tmp_path)
    path = packet / "dense-hard-evaluation-adjudication.v2.1.json"
    value = _read(path)
    value["protocolFair"]["semanticEditCounts"]["total"] += 1
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_artifact(path, packet)
