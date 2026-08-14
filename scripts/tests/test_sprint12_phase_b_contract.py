"""Contract checks for the Sprint 12 Phase B/G1 packet."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/sprint-plans/sprint-12.md"
PACKET = ROOT / "docs/sprint-plans/sprint-12/g1-dataset-contract.md"
AUDIT = ROOT / "docs/ontology/sprint-12-reuse-gap-audit.md"
EVALUATION = ROOT / "evaluation/sprint-12"
ARTIFACTS = ROOT / "docs/sprint-plans/sprint-12/artifacts"


def test_phase_b_tasks_are_complete_but_g1_approval_is_pending() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    for number in range(11, 28):
        assert f"[x] **S12-{number:02d}" in plan
    assert "[ ] **S12-28" in plan
    assert "G1_PACKET_READY_FOR_HUMAN_APPROVAL" in plan


def test_g1_packet_contains_contract_sections_and_pending_approval() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    for section in [
        "Contract package (S12-11 through S12-27)",
        "Dataset envelope and splits",
        "Annotation and adjudication contract",
        "Deterministic validation rules (S12-23)",
        "Pre-registered thresholds (S12-25)",
        "Ontology and semantic review (S12-26)",
        "G1 acceptance checklist",
        "Approval record (S12-28)",
    ]:
        assert section in packet
    assert "| G1 outcome | `PENDING_HUMAN_APPROVAL` |" in packet
    assert "[ ] Project owner and semantic reviewer approve the G1 dataset contract." in packet


def test_phase_b_json_contracts_are_valid_and_versioned() -> None:
    atomic = json.loads((EVALUATION / "schema/atomic-case.schema.json").read_text(encoding="utf-8"))
    scenario = json.loads((EVALUATION / "schema/scenario-case.schema.json").read_text(encoding="utf-8"))
    coverage = json.loads((EVALUATION / "coverage-matrix.v1.json").read_text(encoding="utf-8"))
    assert atomic["$id"].endswith("atomic-case.v1.schema.json")
    assert scenario["$id"].endswith("scenario-case.v1.schema.json")
    assert coverage["version"] == "s12.coverage.v1"
    assert len(coverage["journeys"]) == 8
    assert coverage["minimums"]["atomicCases"] == 200
    assert coverage["minimums"]["longitudinalScenarios"] == 24


def test_ontology_audit_is_no_change_and_pending_semantic_review() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    assert "**Status:** `PENDING_HUMAN_REVIEW`" in audit
    assert "No ontology vocabulary change is proposed" in audit
    assert "Keep operational/evaluation" in audit
    assert "[ ] Approve reuse/no-change semantic outcome." in audit


def test_phase_b_task_summaries_exist() -> None:
    for number in range(11, 28):
        summary = ARTIFACTS / f"task_S12-{number:02d}_summary.md"
        assert summary.exists(), summary
        content = summary.read_text(encoding="utf-8")
        assert f"S12-{number:02d}" in content
        assert "## Testing" in content
