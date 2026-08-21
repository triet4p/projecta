from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_V6 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v6.json"
REPORT_V9 = ROOT / "evaluation/sprint-12/optimization/s12-f-12-stage-a-report.v9.json"
ARTIFACT = ROOT / "evaluation/sprint-12/optimization/s12-f-12-rm48-error-comparison.v1.json"
SNAPSHOT = ROOT / "evaluation/sprint-12/current-state-next-rm48.v1.json"
PACKET = ROOT / "evaluation/sprint-12/optimization/g5-packet.v34.rm48-preparation.json"

import sys

sys.path.insert(0, str(ROOT / "scripts"))

from s12_f12_rm48_error_comparison import build_comparison, digest  # noqa: E402


def test_rm48_artifact_is_deterministic_and_binds_immutable_reports() -> None:
    generated = build_comparison()
    persisted = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert generated == persisted
    assert digest(REPORT_V6) == generated["sources"]["v6"]["digest"]
    assert digest(REPORT_V9) == generated["sources"]["v9"]["digest"]
    assert generated["sources"]["v6"]["immutable"] is True
    assert generated["sources"]["v9"]["immutable"] is True


def test_rm48_accounting_and_failure_clusters_reconcile() -> None:
    report = build_comparison()
    accounting = report["accountingComparison"]
    assert accounting["v6"]["providerCallsAttempted"] == 144
    assert accounting["v9"]["providerCallsAttempted"] == 144
    assert accounting["v6"]["retryCount"] == accounting["v9"]["retryCount"] == 0
    assert accounting["deltaV9MinusV6"]["schemaInvalid"] == -1
    failures = report["failureComparison"]
    assert failures["schemaInvalid"]["v6Total"] == 6
    assert failures["schemaInvalid"]["v9Total"] == 5
    assert failures["invalidEvidence"]["v6Total"] == 17
    assert failures["invalidEvidence"]["v9Total"] == 20
    assert failures["invalidEvidence"]["v9ReasonCounts"] == {
        "evidence_does_not_contain_endpoints": 6,
        "evidence_does_not_contain_trigger": 14,
    }


def test_rm48_non_authoritative_snapshots_bind_comparison_and_execution_history() -> None:
    comparison_digest = digest(ARTIFACT)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    assert snapshot["role"] == "NON_AUTHORITATIVE_PREPARATION_SNAPSHOT"
    assert snapshot["comparison"]["digest"] == comparison_digest
    assert packet["comparison"]["digest"] == comparison_digest
    assert snapshot["authority"]["executionTransition"]["digest"] == (
        "sha256:948a2f1aa1015e339692e113feb878949eb0a9b080174d0ef9cfabeca378ea95"
    )
    assert packet["executionTransition"]["digest"] == snapshot["authority"]["executionTransition"]["digest"]


def test_rm48_control_and_governance_are_fail_closed() -> None:
    report = build_comparison()
    control = report["goldRelationsControl"]
    assert control["v6"] == {"integrityPass": True, "invalidEvidence": 0, "thresholdsPass": True}
    assert control["v9"] == {"integrityPass": True, "invalidEvidence": 0, "thresholdsPass": True}
    governance = report["governance"]
    assert governance["offlineComparisonPrepared"] is True
    assert all(not governance[key] for key in governance if key != "offlineComparisonPrepared")
    assert report["nextGate"] == "S12-RM-49_OWNER_REVIEW_OFFLINE_ERROR_ANALYSIS_PREPARATION"


def test_rm48_does_not_emit_raw_data_or_claim_causality() -> None:
    report = build_comparison()
    encoded = json.dumps(report, ensure_ascii=False).lower()
    for forbidden in ("rawproviderpayload", "rawsourcetext", "rawtriggerquote", "rawvalidationdetail"):
        assert forbidden in encoded  # explicit false policy fields are retained
    assert report["analysisBoundary"]["rawProviderPayloadIncluded"] is False
    assert report["analysisBoundary"]["rawSourceTextIncluded"] is False
    assert report["analysisBoundary"]["causalityClaim"].startswith("unknown")
    assert report["remediationOptions"][-1]["id"] == "C"
