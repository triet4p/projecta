"""Deterministic v3 evaluator regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluate_s12_dense_hard_v3 import (
    PACKET,
    evaluate,
    normalize_evidence,
    validate_evaluation_artifact,
)


def test_frozen_evaluation_recomputes_byte_for_byte() -> None:
    value = validate_evaluation_artifact()
    assert (
        value["candidateDigest"]
        == "sha256:c24442f09ba8c099532931dde26d53d08c9fc9b64583c512540d4fba99b32782"
    )
    assert value["counts"]["caseCount"] == 30
    assert len(value["perSlice"]) == 22


def test_v3_identity_and_type_diagnostics_do_not_cascade() -> None:
    value = evaluate()
    assert value["entityMetrics"]["tp"] == 97
    assert value["relationMetrics"]["tp"] == 37
    assert value["typeDiagnostics"]["cascadeToRelation"] is False
    assert value["typeDiagnostics"]["typeCorrections"] == 35


def test_formatting_and_terminal_punctuation_are_unchanged() -> None:
    assert normalize_evidence("  A\n B.!! ") == "A B"
    value = evaluate()
    assert value["errorTaxonomy"]["counts"]["RELATION_EVIDENCE_MISMATCH"] == 0


def test_evaluation_artifact_is_immutable(tmp_path: Path) -> None:
    artifact = json.loads((PACKET / "dense-hard-evaluation.v3.json").read_text(encoding="utf-8"))
    artifact["counts"]["caseCount"] = 29
    path = tmp_path / "dense-hard-evaluation.v3.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_evaluation_artifact(path)


def test_candidate_digest_tampering_fails_closed(tmp_path: Path) -> None:
    candidate = json.loads((PACKET / "dense-hard-candidate.v3.json").read_text(encoding="utf-8"))
    candidate["records"][0]["abstention"] = "full"
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate digest"):
        evaluate(path)
