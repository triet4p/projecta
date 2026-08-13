"""Provision one single-use, credential-free GitHub Public Issues setup handle."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from projecta_api.config import Settings
from projecta_api.connectors.github_public_issues import GitHubPublicIssuesInstallationConfig
from projecta_api.connectors.github_public_issues_setup import (
    PostgresGitHubPublicIssuesSetupRegistry,
)
from projecta_api.operational.database import ConnectorDatabase


class GitHubSetupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    actor_id: str = Field(alias="actorId", min_length=1, max_length=128)
    owner: str = Field(min_length=1, max_length=39)
    repository: str = Field(min_length=1, max_length=100)
    installation_id: str | None = Field(default=None, alias="installationId", max_length=128)
    expected_revision: int = Field(default=1, alias="expectedRevision", ge=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision an opaque GitHub Public Issues setup handle")
    parser.add_argument("input", type=Path, help="untracked operator JSON input")
    parser.add_argument("--output-handle-file", type=Path, required=True)
    args = parser.parse_args()
    if args.output_handle_file.exists():
        raise SystemExit("output handle file already exists")
    payload = GitHubSetupInput.model_validate_json(args.input.read_text(encoding="utf-8"))
    config = GitHubPublicIssuesInstallationConfig(owner=payload.owner, repository=payload.repository)
    installation_id = payload.installation_id or "github-acceptance-" + uuid4().hex
    handle = PostgresGitHubPublicIssuesSetupRegistry(ConnectorDatabase(Settings())).issue(
        payload.project_id,
        payload.actor_id,
        installation_id,
        config,
        expected_revision=payload.expected_revision,
    )
    args.output_handle_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_handle_file.write_text(handle + "\n", encoding="utf-8")
    os.chmod(args.output_handle_file, 0o600)
    print("GitHub Public Issues setup handle written to the restricted output file; no provider credential was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
