"""Contract checks for the Sprint 12 Phase C/G2 pilot packet."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/sprint-plans/sprint-12.md"
PACKET = ROOT / "docs/sprint-plans/sprint-12/g2-annotation-pilot.md"
PILOT = ROOT / "evaluation/sprint-12/pilot"
ARTIFACTS = ROOT / "docs/sprint-plans/sprint-12/artifacts"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase_c_tasks_are_complete_but_g2_approval_is_pending() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    for number in range(29, 39):
        assert f"[x] **S12-{number:02d}" in plan
    assert "[ ] **S12-39" in plan
    assert "G2_PACKET_READY_FOR_HUMAN_APPROVAL" in plan


def test_pilot_has_twenty_cases_three_scenarios_and_real_digests() -> None:
    atomic = _read_json(PILOT / "atomic-pilot.v1.json")
    scenarios = _read_json(PILOT / "scenario-pilot.v1.json")
    assert atomic["status"] == "AGENT_GENERATED_CALIBRATION_FIXTURE"
    assert len(atomic["cases"]) == 20
    assert len({case["caseId"] for case in atomic["cases"]}) == 20
    assert {case["source"]["language"] for case in atomic["cases"]} == {"vi", "en", "ja", "mixed"}
    for case in atomic["cases"]:
        source = case["source"]
        digest = hashlib.sha256(source["rawText"].encode("utf-8")).hexdigest()
        assert source["contentDigest"] == f"sha256:{digest}"
        for item in case["gold"]["entities"] + case["gold"]["relations"] + case["gold"]["links"]:
            span = item["span"]
            assert source["rawText"][span["start"] : span["end"]] == span["text"]
            assert span["start"] < span["end"]
    assert len(scenarios["scenarios"]) == 3
    assert all(len(scenario["events"]) == 5 for scenario in scenarios["scenarios"])


def test_fixture_labels_and_agreement_report_are_explicitly_nonhuman() -> None:
    label_a = _read_json(PILOT / "labels/annotator-a.v1.json")
    label_b = _read_json(PILOT / "labels/annotator-b.v1.json")
    report = _read_json(PILOT / "agreement-report.v1.json")
    assert len(label_a["cases"]) == len(label_b["cases"]) == 20
    assert label_a["humanEvidence"] is False
    assert label_b["humanEvidence"] is False
    assert report["humanEvidence"] is False
    assert report["fixturePassesProvisionalThresholds"] is True
    assert report["spanF1"] >= report["provisionalThresholds"]["spanF1"]
    assert report["relationLinkF1"] >= report["provisionalThresholds"]["relationLinkF1"]
    assert _read_json(PILOT / "adjudication-log.v1.json")["unresolvedDisagreements"] == 0


def test_g2_packet_requires_human_evidence_and_keeps_gate_pending() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    for section in [
        "Pilot package",
        "Fixture validation and provisional results",
        "Human evidence required for G2",
        "G2 acceptance checklist",
        "Approval record (S12-39)",
    ]:
        assert section in packet
    assert "| G2 outcome | `PENDING_HUMAN_APPROVAL` |" in packet
    assert "- [ ] Qualified human annotation evidence is supplied." in packet
    assert "- [ ] Human reviewers approve G2 annotation reliability." in packet


def test_phase_c_summaries_and_guide_revision_exist() -> None:
    for number in range(29, 39):
        summary = ARTIFACTS / f"task_S12-{number:02d}_summary.md"
        assert summary.exists(), summary
        content = summary.read_text(encoding="utf-8")
        assert f"S12-{number:02d}" in content
        assert "## Testing" in content
    guide = (PILOT / "annotation-guide.v1.1.md").read_text(encoding="utf-8")
    assert "AG-01" in guide
    assert "AG-02" in guide
