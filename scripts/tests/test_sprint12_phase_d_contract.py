"""Contract checks for the Sprint 12 Phase D corpus and G3 packet."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/sprint-plans/sprint-12.md"
CORPUS = ROOT / "evaluation/sprint-12/corpus"
PACKET = ROOT / "docs/sprint-plans/sprint-12/g3-dataset-freeze.md"

_VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "sprint12_phase_d_validator", ROOT / "scripts/validate_sprint12_phase_d.py"
)
assert _VALIDATOR_SPEC is not None and _VALIDATOR_SPEC.loader is not None
_VALIDATOR_MODULE = importlib.util.module_from_spec(_VALIDATOR_SPEC)
_VALIDATOR_SPEC.loader.exec_module(_VALIDATOR_MODULE)
validate = _VALIDATOR_MODULE.validate


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase_d_tasks_stop_at_human_g3_gate() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    assert "Status: `G3_APPROVED_G4_PENDING`" in plan
    for number in range(40, 49):
        assert f"[x] **S12-{number:02d}" in plan
    for number in (49, 50):
        assert f"[ ] **S12-{number:02d}" in plan
    for number in range(51, 55):
        assert f"[x] **S12-{number:02d}" in plan
    assert "[ ] **S12-55" in plan
    assert "[x] **S12-56" in plan
    assert "[x] **S12-57" in plan


def test_phase_d_validator_passes_without_claiming_human_evidence() -> None:
    result = validate()
    assert result == {
        "status": "PASS_WITH_HUMAN_GATES_PENDING",
        "atomicPayloadCases": 160,
        "atomicManifestCases": 200,
        "scenarioPayloadEpisodes": 18,
        "scenarioManifestEpisodes": 24,
        "testCustody": "not-established",
        "humanEvidence": False,
    }


def test_phase_d_manifests_and_gold_artifacts_are_bound() -> None:
    manifest = read_json(CORPUS / "manifest.v1.json")
    custody = read_json(CORPUS / "manifests/test-custody.manifest.v1.json")
    assert manifest["atomicCounts"] == {
        "development": 120,
        "validation": 40,
        "test": 40,
        "total": 200,
    }
    assert manifest["scenarioCounts"] == {
        "development": 12,
        "validation": 6,
        "test": 6,
        "total": 24,
    }
    assert manifest["qualifiedHumanEvidence"] is False
    assert custody["payloadPresent"] is False
    for relative in [
        "gold/atomic-gold.v1.json",
        "gold/scenario-gold.v1.json",
        "gold/retrieval-gold.v1.json",
        "gold/business-review-gold.v1.json",
        "qa/qa-report.v1.json",
        "qa/adjudication-log.v1.json",
        "manifests/development-validation.manifest.v1.json",
        "manifests/test-custody.manifest.v1.json",
        "validation/report.v1.json",
    ]:
        assert (CORPUS / relative).exists(), relative


def test_g3_packet_records_approval_with_explicit_limitations() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    assert "**Status:** `G3_APPROVED_G4_PENDING`" in packet
    assert "PASS_WITH_HUMAN_GATES_PENDING" in packet
    assert "| G3 outcome | `APPROVED_WITH_LIMITATIONS` |" in packet
    assert "Test payloads" in packet
    assert "and gold are intentionally absent from the repository" in packet
    assert (
        "- [x] Project owner approves G3 with the limitations recorded above." in packet
    )
    assert "- [ ] Human data reviewer accepts the exact dataset version." in packet
