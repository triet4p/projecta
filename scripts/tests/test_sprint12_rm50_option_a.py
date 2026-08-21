from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
V9 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"
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


def test_option_a_rejects_v9_invalid_evidence_count_mutation() -> None:
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    v9 = json.loads(V9.read_text(encoding="utf-8"))
    target = next(case for case in v9["caseRecords"] if case["arms"]["gold-entities"]["invalidEvidenceCount"])
    target["arms"]["gold-entities"]["invalidEvidenceCount"] += 1
    with pytest.raises(ValueError, match="matrix"):
        build_report(v6, v9)


def test_option_a_rejects_v6_invalid_evidence_count_mutation() -> None:
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    v9 = json.loads(V9.read_text(encoding="utf-8"))
    target = next(case for case in v6["caseRecords"] if case["arms"]["gold-entities"]["invalidEvidenceCount"])
    target["arms"]["gold-entities"]["invalidEvidenceCount"] += 1
    with pytest.raises(ValueError, match="matrix"):
        build_report(v6, v9)


@pytest.mark.parametrize("source", ["v6", "v9"])
@pytest.mark.parametrize("mutation", ["caseId", "runId", "arm", "stage"])
def test_option_a_rejects_source_identity_mutations(source: str, mutation: str) -> None:
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    v9 = json.loads(V9.read_text(encoding="utf-8"))
    report = v6 if source == "v6" else v9
    case = report["caseRecords"][0]
    if mutation == "caseId":
        case["caseId"] = "s12-a-9999"
    elif mutation == "runId":
        case["runId"] += 1
    elif mutation == "arm":
        case["arms"]["unexpected-arm"] = case["arms"].pop("gold-entities")
    else:
        case["arms"]["predicted-entities"]["stage-extra"] = case["arms"]["predicted-entities"].pop("stage1")
    with pytest.raises(ValueError, match="matrix|identity"):
        build_report(v6, v9)


@pytest.mark.parametrize("source", ["v6", "v9"])
@pytest.mark.parametrize("operation", ["duplicate", "delete", "add"])
def test_option_a_rejects_source_case_matrix_set_mutations(source: str, operation: str) -> None:
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    v9 = json.loads(V9.read_text(encoding="utf-8"))
    report = v6 if source == "v6" else v9
    if operation == "duplicate":
        report["caseRecords"].append(deepcopy(report["caseRecords"][0]))
    elif operation == "delete":
        report["caseRecords"].pop()
    else:
        added = deepcopy(report["caseRecords"][0])
        added["caseId"] = "s12-a-9999"
        added["runId"] = 1
        report["caseRecords"].append(added)
    with pytest.raises(ValueError, match="matrix|identity"):
        build_report(v6, v9)


@pytest.mark.parametrize("source", ["v6", "v9"])
def test_option_a_rejects_cross_swapped_stage_identity(source: str) -> None:
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    v9 = json.loads(V9.read_text(encoding="utf-8"))
    report = v6 if source == "v6" else v9
    case = next(case for case in report["caseRecords"] if case["arms"]["predicted-entities"]["stage1"].get("failureClass"))
    arm = case["arms"]["predicted-entities"]
    arm["stage1"], arm["stage2"] = arm["stage2"], arm["stage1"]
    with pytest.raises(ValueError, match="matrix|identity"):
        build_report(v6, v9)


def test_option_a_rejects_v9_schema_finding_removal() -> None:
    v6 = json.loads(V6.read_text(encoding="utf-8"))
    v9 = json.loads(V9.read_text(encoding="utf-8"))
    target = next(
        case["arms"]["predicted-entities"]["stage1"]
        for case in v9["caseRecords"]
        if case["arms"]["predicted-entities"]["stage1"].get("failureClass")
    )
    target["failureClass"] = None
    with pytest.raises(ValueError, match="matrix"):
        build_report(v6, v9)


@pytest.mark.parametrize("mutation", ["schemaClusterDelta", "evidenceClusterDelta", "schemaReasonCounts", "evidenceReasonCounts"])
def test_option_a_rejects_direct_diagnostic_cluster_or_reason_mutations(mutation: str) -> None:
    report = build_report()
    candidate = deepcopy(report)
    if mutation.endswith("ClusterDelta"):
        first_key = next(iter(candidate["diagnostics"][mutation]))
        candidate["diagnostics"][mutation][first_key]["v9Count"] += 1
    else:
        reason = "validation_detail_unavailable" if mutation == "schemaReasonCounts" else "materializer_detail_unavailable"
        candidate["diagnostics"][mutation]["v9"][reason] += 1
    with pytest.raises(ValueError, match="does not match"):
        validate_report(candidate)
