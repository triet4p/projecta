"""Contract tests for the immutable Sprint 12 S12-R01 audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "evaluation/sprint-12/audit/core-quality-audit.v1.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_audit_binds_existing_artifacts_without_raw_payloads() -> None:
    audit = read_json(AUDIT)

    assert audit["schemaVersion"] == "s12.core-quality-audit.v1"
    assert audit["status"] == "G3.1_REMEDIATION_REQUIRED_G5_PAUSED"
    assert audit["scope"]["historicalEvidenceImmutable"] is True
    assert audit["scope"]["providerExecutionPerformed"] is False
    assert audit["scope"]["heldOutInspected"] is False

    artifacts = audit["sourceArtifacts"]
    assert len(artifacts) >= 20
    assert len({item["id"] for item in artifacts}) == len(artifacts)
    for item in artifacts:
        source = ROOT / item["path"]
        assert source.is_file(), item["path"]
        if item.get("currentSourceMayEvolve") is True:
            assert item["binding"] == "historical-at-r01-publication"
            continue
        assert item["digest"] == digest(source), item["path"]

    serialized = json.dumps(audit, ensure_ascii=False).lower()
    assert '"rawtext"' not in serialized
    assert '"apikey"' not in serialized
    assert '"providerpayload"' not in serialized


def test_audit_records_the_dataset_and_scenario_blockers() -> None:
    observations = read_json(AUDIT)["observations"]
    atomic = observations["atomicCorpusV2"]
    assert atomic["caseCount"] == 160
    assert atomic["abstentionCases"] == 98
    assert atomic["relationPositiveCases"] == 20
    assert atomic["artificialMarkerCases"] == 160
    assert atomic["normalizedTemplateAudit"]["largestSixTemplateClustersCaseCount"] == 119
    assert atomic["normalizedTemplateAudit"]["validationCasesWithDevelopmentTemplate"] == 31

    scenarios = observations["scenarioCorpusV2"]
    assert scenarios["scenarioCount"] == 18
    assert scenarios["uniqueSourceSequences"] == 6
    assert scenarios["sourceSequenceReuseCount"] == 3
    assert scenarios["unexplainedGoldVariation"] is True


def test_audit_binds_all_f08_case_runs_and_preserves_rejection_boundary() -> None:
    audit = read_json(AUDIT)
    aggregate = read_json(
        ROOT / "evaluation/sprint-12/optimization/s12-f-08-relation-prompt-stage-a.v1.json"
    )
    bound = {item["path"]: item["digest"] for item in audit["sourceArtifacts"]}
    report_paths = [
        run["reportPath"]
        for arm in (aggregate["control"], aggregate["candidate"])
        for run in arm["runs"]
    ]
    assert len(report_paths) == 6
    assert len(set(report_paths)) == 6
    for report_path in report_paths:
        assert report_path in bound
        assert bound[report_path] == digest(ROOT / report_path)

    f08 = audit["observations"]["f08StageA"]
    assert f08["executionCount"] == 96
    assert f08["hardGateFailures"] == 0
    assert f08["supersessionFalsePositiveCount"] == 0
    assert f08["heldOutInspected"] is False
    assert f08["stageBAuthorized"] is False
    assert f08["candidateSelection"] == "NO_SELECTION"
    assert f08["decision"] == "STAGE_A_NOT_ELIGIBLE_FOR_STAGE_B"


def test_audit_records_diagnostic_relation_decomposition_as_non_official() -> None:
    diagnostic = read_json(AUDIT)["observations"]["relationDiagnostic"]
    assert diagnostic["status"] == "diagnostic_not_official_metric"
    assert diagnostic["goldRelationsPerArm"] == 21
    assert diagnostic["exactMatchesPerArm"] == 1
    assert diagnostic["predicateAndEndpointMatchesWithSpanMismatchPerArm"] == 19
    assert diagnostic["missingRelationsPerArm"] == 1


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
