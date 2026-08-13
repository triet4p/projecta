"""Provision one single-use Teams setup handle from operator-controlled input."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from projecta_api.config import Settings
from projecta_api.configuration.ports import SecretScope
from projecta_api.connectors.teams_auth import TeamsCertificateCredential
from projecta_api.connectors.teams_setup import PostgresTeamsSetupRegistry
from projecta_api.operational.database import ConnectorDatabase
from projecta_api.secrets.openbao import OpenBaoHttpTransport, OpenBaoSecretStore
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TeamsSetupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project_id: str = Field(alias="projectId", min_length=1, max_length=128)
    installation_id: str = Field(alias="installationId", min_length=1, max_length=128)
    team_id: str = Field(alias="teamId", min_length=1, max_length=256)
    channel_id: str = Field(alias="channelId", min_length=1, max_length=256)
    credential_revision: int = Field(default=1, alias="credentialRevision", ge=1)
    credential: TeamsCertificateCredential


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision an opaque Teams setup handle")
    parser.add_argument("input", type=Path, help="untracked operator JSON input")
    parser.add_argument("--operator-token-file", type=Path, required=True)
    parser.add_argument("--output-handle-file", type=Path, required=True)
    args = parser.parse_args()
    if args.output_handle_file.exists():
        raise SystemExit("output handle file already exists")
    payload = TeamsSetupInput.model_validate_json(args.input.read_text(encoding="utf-8"))
    token = _restricted_material(args.operator_token_file)
    settings = Settings()
    if settings.openbao_url is None:
        raise SystemExit("OpenBao configuration is required")
    scope = SecretScope(
        payload.project_id,
        payload.installation_id,
        "teams",
        payload.credential.tenant_id,
        payload.credential_revision,
    )
    store = OpenBaoSecretStore(
        OpenBaoHttpTransport(
            str(settings.openbao_url),
            lambda: token,
            verify=str(settings.openbao_ca_file),
        )
    )
    snapshot = store.create_scoped(
        scope,
        SecretStr(payload.credential.model_dump_json(by_alias=True)),
    )
    registry = PostgresTeamsSetupRegistry(ConnectorDatabase(settings))
    handle = registry.issue(
        payload.project_id,
        payload.installation_id,
        {
            "tenantId": payload.credential.tenant_id,
            "teamId": payload.team_id,
            "channelId": payload.channel_id,
            "secretReference": snapshot.reference,
            "credentialRevision": payload.credential_revision,
            "capabilities": ["inbound-import"],
        },
    )
    args.output_handle_file.parent.mkdir(parents=True, exist_ok=True)
    args.output_handle_file.write_text(handle + "\n", encoding="utf-8")
    os.chmod(args.output_handle_file, 0o600)
    print("Teams setup handle written to the restricted output file; no provider value was printed.")
    return 0


def _restricted_material(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value or len(value) > 512 or any(character.isspace() for character in value):
        raise SystemExit("operator token file is invalid")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
