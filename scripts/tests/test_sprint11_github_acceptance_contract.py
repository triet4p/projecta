"""Static contract for the credential-free GitHub live acceptance runner."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_github_acceptance_runner_is_credential_free_and_sanitized() -> None:
    script = (ROOT / "scripts/run_sprint11_github_public_issues_acceptance.ps1").read_text(
        encoding="utf-8"
    )
    for marker in (
        "github-public-issues",
        "githubSetupHandle",
        "repositoryHash",
        "credentialsPersisted = $false",
        "rawProviderPayload = $false",
        "projectHandlePersisted = $false",
        "generatedBy = \"scripts/run_sprint11_github_public_issues_acceptance.ps1\"",
        "evidence-candidate-continuity",
        "The first live run did not import exactly the provider snapshot event count.",
        "Deliberately no Authorization header",
    ):
        assert marker in script
    assert "[string]$Token" not in script
    assert "Authorization =" not in script
    assert "/user" not in script


def test_edit_journey_waits_for_provider_visibility_before_running() -> None:
    script = (ROOT / "scripts/run_sprint11_github_public_issues_edit_journey.ps1").read_text(
        encoding="utf-8"
    )
    assert "function Wait-ForProviderVisibility" in script
    assert "Wait-ForProviderVisibility $issue $comment" in script


def test_github_acceptance_runner_has_no_provider_write_surface() -> None:
    script = (ROOT / "scripts/run_sprint11_github_public_issues_acceptance.ps1").read_text(
        encoding="utf-8"
    )
    assert "api.github.com" in script
    assert "Invoke-GitHubCollection" in script
    assert "issues" not in script.split("Invoke-Projecta", 1)[0]


def test_isolation_assertions_accept_structured_404_problem_responses() -> None:
    acceptance = (ROOT / "scripts/run_sprint11_github_public_issues_acceptance.ps1").read_text(
        encoding="utf-8"
    )
    journey = (ROOT / "scripts/run_sprint11_github_public_issues_edit_journey.ps1").read_text(
        encoding="utf-8"
    )
    for script in (acceptance, journey):
        assert "ErrorDetails.Message" in script
        assert "CONNECTOR_NOT_FOUND" in script
