"""Contract checks for Sprint 11 discovery artifacts and G1 approval."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SPRINT_PLAN = ROOT / "docs" / "sprint-plans" / "sprint-11.md"
ARTIFACTS = {
    "S11-01": ROOT / "docs" / "architecture" / "v0.5.1-compatibility-baseline.md",
    "S11-02": ROOT / "docs" / "use-cases" / "teams-read-only-channel.md",
    "S11-03": ROOT / "docs" / "architecture" / "sprint-11-identity-context-seam-audit.md",
    "S11-04": ROOT / "docs" / "architecture" / "oidc-provider-benchmark.md",
    "S11-05": ROOT / "docs" / "architecture" / "production-identity-contract.md",
    "S11-06": ROOT / "docs" / "architecture" / "project-membership-capability-policy.md",
    "S11-07": ROOT / "docs" / "architecture" / "identity-threat-model-sprint-11.md",
    "S11-08": ROOT / "docs" / "architecture" / "secret-provider-benchmark-sprint-11.md",
    "S11-09": ROOT / "docs" / "architecture" / "secret-manager-contract.md",
    "S11-10": ROOT / "docs" / "architecture" / "openbao-operations-proposal.md",
    "S11-11": ROOT / "docs" / "architecture" / "teams-provider-contract.md",
    "S11-12": ROOT / "docs" / "architecture" / "teams-connector-threat-model.md",
    "S11-13": ROOT / "docs" / "ontology" / "sprint-11-teams-reuse-audit.md",
}


def test_phase_a_artifacts_are_present_and_approved_or_frozen() -> None:
    for task, path in ARTIFACTS.items():
        content = path.read_text(encoding="utf-8")
        assert task in content
        assert any(
            marker in content
            for marker in (
                "G1_APPROVED",
                "G1_APPROVED_WITH_REVISIONS",
                "FROZEN_FOR_SPRINT_11_DISCOVERY",
            )
        )


def test_phase_a_packet_indexes_every_task() -> None:
    packet = (ROOT / "docs" / "sprint-plans" / "sprint-11" / "phase-a-review-packet.md").read_text(
        encoding="utf-8"
    )
    for task in ARTIFACTS:
        assert task in packet
    assert "S11-14" in packet
    assert "implementation tasks S11-15" in packet


def test_phase_a_through_f_implementation_boundaries_are_done_but_drills_are_pending() -> None:
    plan = SPRINT_PLAN.read_text(encoding="utf-8")
    for task in ARTIFACTS:
        assert f"- [x] **{task}" in plan
    assert "- [x] **S11-14" in plan
    for number in (*range(15, 30), *range(30, 40), *range(40, 51), *range(51, 58), 58, 59, 60, 61, 62, 64, 65, 66, 68):
        assert re.search(rf"- \[(?:x|~)\] \*\*S11-{number}\b", plan)
    assert "- [x] **S11-63" in plan
    assert "- [ ] **S11-67" in plan


def test_discovery_packet_preserves_non_goals_and_no_ontology_default() -> None:
    packet = (ROOT / "docs" / "sprint-plans" / "sprint-11" / "phase-a-review-packet.md").read_text(
        encoding="utf-8"
    )
    ontology = ARTIFACTS["S11-13"].read_text(encoding="utf-8")
    assert "NO_ONTOLOGY_CHANGE_REQUIRED" in ontology
    assert "G1_APPROVED_WITH_REVISIONS" in packet


def test_g1_approval_records_revisions_and_durable_decision() -> None:
    approval = (ROOT / "docs" / "sprint-plans" / "sprint-11" / "g1-approval.md").read_text(
        encoding="utf-8"
    )
    decisions = (ROOT / ".agents" / "memory" / "decisions.md").read_text(encoding="utf-8")
    for marker in (
        "Keycloak `26.7.0`",
        "OpenBao `2.6.1`",
        "ChannelMessage.Read.Group",
        "service-level custody boundary",
        "invalidate all Projecta sessions",
        "NO_ONTOLOGY_CHANGE_REQUIRED",
    ):
        assert marker in approval
        assert marker in decisions


def test_phase_a_local_markdown_links_resolve() -> None:
    review_files = [
        *ARTIFACTS.values(),
        ROOT / "docs" / "sprint-plans" / "sprint-11" / "phase-a-review-packet.md",
        *(
            ROOT / "docs" / "sprint-plans" / "sprint-11" / "artifacts"
        ).glob("task_S11-*_summary.md"),
    ]
    for path in review_files:
        content = path.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in target or target.startswith("#"):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if re.match(r"^/[A-Za-z]:/", target_path):
                candidate = Path(target_path[1:])
            elif re.match(r"^[A-Za-z]:/", target_path):
                candidate = Path(target_path)
            else:
                candidate = path.parent / target_path
            assert candidate.resolve().is_file(), (
                f"broken local link in {path}: {target}"
            )
