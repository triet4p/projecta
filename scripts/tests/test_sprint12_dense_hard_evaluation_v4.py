"""Regression tests for the immutable dense-hard v4 evaluation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluate_s12_dense_hard_v4 import (
    PACKET,
    evaluate,
    normalize_evidence,
    validate_evaluation_artifact,
)


def test_frozen_v4_evaluation_recomputes_and_fails_both_strata() -> None:
    value = validate_evaluation_artifact()
    assert value["candidateDigest"] == "sha256:c1a3618eec4cfb0657c738b3dff6233a011a0ff7ae1bbe661b7a21490c4e4e35"
    assert value["counts"]["caseCount"] == 32
    assert value["utilityGate"]["pass"] is False
    assert value["safetyGate"]["pass"] is False
    assert value["overallPass"] is False
    assert value["v3_1Comparison"]["pooled"] is False


def test_v4_occurrence_type_and_evidence_rules_are_explicit() -> None:
    value = evaluate()
    assert value["typeDiagnostics"]["identityIndependentOfType"] is True
    assert value["typeDiagnostics"]["cascadeToRelation"] is False
    assert normalize_evidence("  A\n B.!! ") == "A B"
    assert value["errorTaxonomy"]["counts"]["RELATION_EVIDENCE_MISMATCH"] == 0


def test_candidate_digest_tampering_fails_closed(tmp_path: Path) -> None:
    candidate = json.loads((PACKET / "dense-hard-candidate.v4.json").read_text(encoding="utf-8"))
    candidate["records"][0]["abstention"] = "full"
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate digest"):
        evaluate(path)
