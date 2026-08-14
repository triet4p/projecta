"""Contract checks for the Sprint 12 Phase A/G0 packet."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/sprint-plans/sprint-12.md"
PACKET = ROOT / "docs/sprint-plans/sprint-12/g0-business-scope.md"
ARTIFACTS = ROOT / "docs/sprint-plans/sprint-12/artifacts"


def test_phase_a_tasks_and_g0_approval_are_complete() -> None:
    plan = PLAN.read_text(encoding="utf-8")
    for task_id in [f"S12-{number:02d}" for number in range(1, 11)]:
        assert f"[x] **{task_id}" in plan
    assert "G0_APPROVED_G1_PENDING" in plan


def test_g0_packet_contains_required_scope_sections_and_approval() -> None:
    packet = PACKET.read_text(encoding="utf-8")
    required_sections = [
        "Released evaluation surface (S12-01)",
        "Buyer-facing hypothesis (S12-02)",
        "Priority business journeys (S12-03)",
        "Target roles and responsibilities (S12-04)",
        "Observable business outcomes (S12-05)",
        "Competency questions and checkpoints (S12-06)",
        "Claims and non-claims (S12-07)",
        "Data-source feasibility (S12-08)",
        "G0 acceptance checklist (S12-09)",
        "Approval record (S12-10)",
    ]
    for section in required_sections:
        assert section in packet
    assert "| G0 outcome | `APPROVED` |" in packet
    assert "[x] Project owner approves the business scope without revisions." in packet
    assert packet.count("| Rank | Journey |") == 1


def test_phase_a_task_summaries_exist() -> None:
    for number in range(1, 11):
        summary = ARTIFACTS / f"task_S12-{number:02d}_summary.md"
        assert summary.exists(), summary
        content = summary.read_text(encoding="utf-8")
        assert f"S12-{number:02d}" in content
        assert "## Testing" in content
