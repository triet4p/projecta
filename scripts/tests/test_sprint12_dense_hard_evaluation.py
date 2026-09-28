"""Fail-closed tests for the offline dense-hard evaluation artifact."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from evaluate_s12_dense_hard_v1 import (
    PACKET,
    evaluate,
    validate_evaluation_artifact,
    write_immutable_evaluation,
)
from jsonschema import Draft202012Validator


def _copy_packet(tmp_path: Path) -> Path:
    target = tmp_path / "dense-hard-v1"
    shutil.copytree(PACKET, target)
    return target


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_evaluation_recomputes_and_meets_strict_schema() -> None:
    artifact = PACKET / "dense-hard-evaluation.v1.json"
    value = validate_evaluation_artifact(artifact)
    schema = _read(PACKET / "dense-hard-evaluation.v1.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    assert value["candidateDigest"] == "sha256:24300cccf1f774329a4bbb2772b2fb952e32e398eec61cf09c060e2eaac7ceba"
    assert value["sourcePayloadDigest"] == "sha256:65e6a044767f97298dee4511d19e3373878483224b9b7cf2606b94acdefc1409"
    assert value["perItemClassificationCounts"] == {"unchanged": 0, "minor": 0, "major": 8, "reject": 2, "abstain": 14}
    assert value["semanticEditCounts"] == {"total": 74, "meanPerCase": 74 / 24}
    assert value["rm67"]["editBurdenGate"] is False
    assert len(value["perSlice"]) == 19
    assert len(value["difficultyTiers"]) == 3


def test_evaluator_is_deterministic_and_does_not_write() -> None:
    first = evaluate(PACKET / "dense-hard-candidate.v1.json")
    second = evaluate(PACKET / "dense-hard-candidate.v1.json")
    assert first == second
    assert write_immutable_evaluation(PACKET) == PACKET / "dense-hard-evaluation.v1.json"


@pytest.mark.parametrize("artifact", ["dense-hard-source-payload.v1.json", "dense-hard-gold.v1.json", "dense-hard-evaluator-manifest.v1.json", "dense-hard-candidate.v1.json"])
def test_binding_mutations_fail_closed(tmp_path: Path, artifact: str) -> None:
    packet = _copy_packet(tmp_path)
    path = packet / artifact
    value = _read(path)
    if artifact.endswith("source-payload.v1.json"):
        value["payloadDigest"] = "sha256:" + "0" * 64
    elif artifact.endswith("gold.v1.json"):
        value["goldDigest"] = "sha256:" + "0" * 64
    elif artifact.endswith("evaluator-manifest.v1.json"):
        value["manifestDigest"] = "sha256:" + "0" * 64
    else:
        value["candidateDigest"] = "sha256:" + "0" * 64
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        evaluate(packet / "dense-hard-candidate.v1.json", packet)


def test_evaluation_mutation_fails_closed(tmp_path: Path) -> None:
    packet = _copy_packet(tmp_path)
    evaluation = packet / "dense-hard-evaluation.v1.json"
    value = _read(evaluation)
    value["semanticEditCounts"]["total"] += 1
    evaluation.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_evaluation_artifact(evaluation, packet)
