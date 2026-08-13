"""Static contract for the credential-free GitHub setup provisioner."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_github_setup_provisioner_is_credential_free() -> None:
    script = (ROOT / "scripts/provision_github_public_issues_setup.py").read_text(encoding="utf-8")
    for marker in (
        "GitHubPublicIssuesInstallationConfig",
        "PostgresGitHubPublicIssuesSetupRegistry",
        "project_id",
        "actor_id",
        "owner",
        "repository",
        "output_handle_file",
    ):
        assert marker in script
    assert "token" not in script.lower()
    assert "Authorization" not in script
    assert "api.github.com" not in script
