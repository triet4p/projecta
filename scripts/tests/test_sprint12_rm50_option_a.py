from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm50-offline-diagnostic-report.v1.json"
SCHEMA = ROOT / "evaluation/sprint-12/harness/s12-f-12-rm50-offline-diagnostic-report.schema.v1.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))

from s12_f12_rm50_offline_diagnostics import (  # noqa: E402
    EVIDENCE_REASON_CODES,
    SCHEMA_REASON_CODES,
    assert_no_raw_data_aliases,
    build_report,
    normalize_evidence_counts,
    normalize_schema_counts,
    validate_report,
)


def test_option_a_report_is_closed_and_reconciled() -> None:
    generated = build_report()
    persisted = json.loads(REPORT.read_text(encoding="utf-8"))
    assert generated == persisted
    validate_report(persisted)
    assert persisted["accounting"]["reconciled"] is True
    assert persisted["diagnostics"]["totalsReconciled"] is True
    assert persisted["stopCriteria"]["allPassed"] is True
    assert persisted["diagnostics"]["schemaReasonCounts"]["v6"]["validation_detail_unavailable"] == 6
    assert persisted["diagnostics"]["evidenceReasonCounts"]["v6"]["materializer_detail_unavailable"] == 17


def test_option_a_finite_reason_allowlists_fail_closed() -> None:
    assert set(normalize_schema_counts({}).keys()) == set(SCHEMA_REASON_CODES)
    assert set(normalize_evidence_counts({}).keys()) == set(EVIDENCE_REASON_CODES)
    with pytest.raises(ValueError):
        normalize_schema_counts({"unregistered_reason": 1})
    with pytest.raises(ValueError):
        normalize_evidence_counts({"unregistered_reason": 1})
    with pytest.raises(ValueError):
        normalize_schema_counts({"validation_detail_unavailable": -1})


def test_option_a_recursively_rejects_raw_dynamic_keys() -> None:
    report = build_report()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(report))
    candidate = deepcopy(report)
    candidate["diagnostics"]["schemaClusterDelta"]["rawSourceText"] = {
        "v6Count": 0,
        "v9Count": 0,
        "overlap": [],
        "newInV9": [],
        "resolvedFromV6": [],
    }
    assert list(validator.iter_errors(candidate))
    with pytest.raises(ValueError):
        assert_no_raw_data_aliases({"dynamic": {"providerPayload": "hidden"}})


def test_option_a_records_j1_gold_entities_transition_and_keeps_governance_closed() -> None:
    report = build_report()
    transition = report["sliceTransitions"]["J1GoldEntitiesEvidence"]
    assert transition["supportRate"] == {"v6": "not-applicable", "v9": 0.0, "transition": "not-applicable_to_zero"}
    assert transition["exactRate"] == {"v6": "not-applicable", "v9": 0.0, "transition": "not-applicable_to_zero"}
    assert all(
        value is False or key in {"offlineOnly", "providerCalls"}
        for key, value in report["governance"].items()
    )
    assert report["governance"]["providerCalls"] == 0

