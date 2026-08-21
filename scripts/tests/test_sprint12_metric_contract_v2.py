"""Contract tests for the frozen Sprint 12 relation metric definitions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "evaluation/sprint-12/harness"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_metric_contract_v2_versions_without_rewriting_v1() -> None:
    contract = read_json(HARNESS / "metric-contract.v2.json")
    audit = read_json(ROOT / "evaluation/sprint-12/audit/core-quality-audit.v1.json")
    historical = next(
        item for item in audit["sourceArtifacts"] if item["id"] == "metric-contract-v1"
    )

    assert contract["version"] == "s12.metric-contract.v2"
    assert contract["supersedes"] == "s12.metric-contract.v1"
    assert contract["historicalContractImmutable"] is True
    assert historical["digest"] == digest(ROOT / historical["path"])
    assert contract["providerExecutionAuthorized"] is False


def test_relation_semantic_identity_excludes_evidence_offsets() -> None:
    relation = read_json(HARNESS / "metric-contract.v2.json")["relationMetrics"]
    semantic = relation["relationSemanticF1"]
    assert semantic["identity"] == [
        "predicate",
        "canonicalSourceEndpoint",
        "canonicalTargetEndpoint",
    ]
    assert semantic["relationEvidenceExcludedFromIdentity"] is True
    assert "startOffset" in semantic["canonicalEndpoint"]
    assert semantic["zeroDenominator"] == (
        "not-applicable only when gold and predicted sets are both empty"
    )


def test_evidence_metrics_are_independent_and_denominator_bound() -> None:
    relation = read_json(HARNESS / "metric-contract.v2.json")["relationMetrics"]
    for name in ("relationEvidenceSupport", "relationEvidenceExact"):
        metric = relation[name]
        assert metric["denominator"] == "semantic relation true positives"
        assert metric["zeroDenominator"] == (
            "not-applicable; never convert to semantic relation zero"
        )
    assert relation["relationEvidenceExact"]["multipleValidSpans"]


def test_contract_requires_reconcilable_per_case_and_slice_reporting() -> None:
    contract = read_json(HARNESS / "metric-contract.v2.json")
    assert contract["aggregation"]["pooledOnlySummaryForbidden"] is True
    assert contract["aggregation"]["aggregateFromPerCaseRecordsOnly"] is True
    assert contract["aggregation"]["metricInferenceFromAggregateForbidden"] is True
    assert "perCaseDenominators" in contract["reportRequirements"]
    assert "perSliceDenominators" in contract["reportRequirements"]


def test_sprint_plan_marks_r01_through_r17_complete_only() -> None:
    plan = (ROOT / "docs/sprint-plans/sprint-12.md").read_text(encoding="utf-8")
    assert "[x] **S12-R01" in plan
    assert "[x] **S12-R02" in plan
    assert "[x] **S12-R03" in plan
    assert "[x] **S12-R04" in plan
    assert "[x] **S12-R05" in plan
    assert "[x] **S12-R06" in plan
    assert "[x] **S12-R07" in plan
    assert "[x] **S12-R08" in plan
    assert "[x] **S12-R09" in plan
    assert "[x] **S12-R10" in plan
    assert "[x] **S12-R11" in plan
    assert "[x] **S12-R12" in plan
    assert "[x] **S12-R13" in plan
    assert "[x] **S12-R14" in plan
    assert "[x] **S12-R15" in plan
    assert "[x] **S12-R16" in plan
    assert "[x] **S12-R17" in plan
    assert "[x] **S12-R18" in plan
    assert "[x] **S12-R19" in plan
    assert "[x] **S12-R20" in plan
    assert "[x] **S12-R21" in plan
    assert "[x] **S12-R22" in plan
    assert "[x] **S12-R23" in plan
    assert "[ ] **S12-R24" in plan
