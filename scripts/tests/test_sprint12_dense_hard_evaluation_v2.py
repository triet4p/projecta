"""Fail-closed tests for the immutable dense-hard v2 evaluation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from evaluate_s12_dense_hard_v2 import (
    PACKET,
    evaluate,
    validate_evaluation_artifact,
    write_immutable_evaluation,
)
from jsonschema import Draft202012Validator


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_packet(tmp_path: Path) -> Path:
    target = tmp_path / "dense-hard-v2"
    shutil.copytree(PACKET, target)
    return target


def test_frozen_v2_evaluation_recomputes_and_meets_strict_schema() -> None:
    value = validate_evaluation_artifact()
    schema = _read(PACKET / "dense-hard-evaluation.v2.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    assert value["candidateDigest"] == "sha256:568f2ff212307b7f88c02706e297fd6567582b8ef498eb7c88f475363a37784d"
    assert value["sourcePayloadDigest"] == "sha256:c5ca7a63ecb16a96e2801ecedc5b20bb02c34705305b301a119ee6f9c05a4232"
    assert value["protocolDigest"] == "sha256:ab9dc5639b87487f4087cd9f36d8ab29aaec17e8eeb2269c4642a8c145f4aa55"
    assert value["perItemClassificationCounts"] == {"unchanged": 0, "minor": 0, "major": 12, "reject": 0, "abstain": 16}
    assert value["semanticEditCounts"] == {"total": 134, "meanPerCase": 134 / 28}
    assert value["quarantineMetrics"]["predictedAssertions"] == 21
    assert value["quarantineMetrics"]["correctAssertions"] == 21
    assert value["quarantineMetrics"]["precision"] == 1.0
    assert value["quarantineMetrics"]["recall"] == 21 / 83
    assert value["rm67"]["editBurdenGate"] is False
    assert len(value["perSlice"]) == 21
    assert len(value["difficultyTiers"]) == 3
    assert value["v1Comparison"]["pooled"] is False


def test_v2_evaluator_is_deterministic_and_does_not_rewrite() -> None:
    first = evaluate()
    second = evaluate()
    assert first == second
    assert write_immutable_evaluation() == PACKET / "dense-hard-evaluation.v2.json"


@pytest.mark.parametrize("artifact", ["dense-hard-source-payload.v2.json", "dense-hard-gold.v2.json", "dense-hard-evaluator-manifest.v2.json", "dense-hard-source-only-protocol.v2.json", "dense-hard-candidate.v2.json"])
def test_v2_binding_mutations_fail_closed(tmp_path: Path, artifact: str) -> None:
    packet = _copy_packet(tmp_path)
    path = packet / artifact
    value = _read(path)
    digest_key = {"dense-hard-source-payload.v2.json": "payloadDigest", "dense-hard-gold.v2.json": "goldDigest", "dense-hard-evaluator-manifest.v2.json": "manifestDigest", "dense-hard-source-only-protocol.v2.json": "protocolDigest", "dense-hard-candidate.v2.json": "candidateDigest"}[artifact]
    value[digest_key] = "sha256:" + "0" * 64
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluate(packet / "dense-hard-candidate.v2.json", packet)


def test_v2_evaluation_mutation_fails_closed(tmp_path: Path) -> None:
    packet = _copy_packet(tmp_path)
    evaluation = packet / "dense-hard-evaluation.v2.json"
    value = _read(evaluation)
    value["semanticEditCounts"]["total"] += 1
    evaluation.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_evaluation_artifact(evaluation, packet)
