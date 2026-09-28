"""Regression tests for the fresh source-only dense-hard v4 packet."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from validate_s12_dense_hard_v4 import PACKET, validate


def test_v4_is_fresh_stratified_source_only_packet() -> None:
    value = validate()
    assert value["caseCount"] == 32
    assert value["utilityCaseCount"] == 24
    assert value["safetyCaseCount"] == 8
    assert value["sliceCount"] >= 22
    assert value["candidateOrEvaluationPresent"] is False
    assert all(value["noReuseChecks"].values())


def test_post_evaluation_packet_lifecycle_is_valid() -> None:
    # The frozen candidate/evaluation are valid post-freeze siblings; only an
    # explicit --pre-candidate audit enforces their absence.
    assert validate()["candidateOrEvaluationPresent"] is False


def test_v4_split_and_protocol_contract_are_bound() -> None:
    manifest = json.loads((PACKET / "dense-hard-evaluator-manifest.v4.json").read_text(encoding="utf-8"))
    protocol = json.loads((PACKET / "dense-hard-source-only-protocol.v4.json").read_text(encoding="utf-8"))
    contract = json.loads((PACKET / "dense-hard-evaluator-contract.v4.json").read_text(encoding="utf-8"))
    assert sum(record["abstentionMode"] == "none" for record in manifest["records"]) == 24
    assert sum(record["abstentionMode"] == "full" for record in manifest["records"]) == 4
    assert sum(record["abstentionMode"] == "partial" for record in manifest["records"]) == 4
    assert protocol["propositionAbstention"]["partial"].startswith("only when explicit unsafe")
    assert protocol["propositionAbstention"]["full"].startswith("only when zero safe")
    assert contract["noCandidateOrEvaluation"] is True


def test_v4_validator_rejects_digest_tampering(tmp_path: Path) -> None:
    for artifact in PACKET.iterdir():
        shutil.copy2(artifact, tmp_path / artifact.name)
    source = json.loads((PACKET / "dense-hard-source-payload.v4.json").read_text(encoding="utf-8"))
    source["records"][0]["rawText"] += " tamper"
    (tmp_path / "dense-hard-source-payload.v4.json").write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError):
        validate(tmp_path)
