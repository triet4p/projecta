"""Regression tests for the immutable v3.1 stratified adjudication."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from adjudicate_s12_dense_hard_v3_1 import OUTPUT, adjudicate, validate


def test_strata_and_overall_gate_are_explicit() -> None:
    value = adjudicate()
    assert value["utilitySubset"]["caseCount"] == 18
    assert value["safetySubset"]["caseCount"] == 12
    assert value["gates"]["utilityRM67"]["pass"] is False
    assert value["gates"]["safety"]["pass"] is True
    assert value["gates"]["overallPass"] is False
    assert value["pooledLegacyDiagnostic"]["authoritative"] is False


def test_frozen_adjudication_recomputes_and_tampering_fails(tmp_path: Path) -> None:
    frozen = json.loads(OUTPUT.read_text(encoding="utf-8"))
    validate(frozen)
    frozen["gates"]["overallPass"] = True
    frozen["adjudicationDigest"] = "sha256:" + "0" * 64
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(ValueError):
        validate(json.loads(path.read_text(encoding="utf-8")))
