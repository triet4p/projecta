"""Failure, abuse, and concurrency injection for the Sprint 11 F boundary."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from projecta_api.config import Settings
from projecta_api.configuration.ports import SecretScope
from projecta_api.connectors.secrets import ConnectorSecretError, ConnectorSecretPolicy
from projecta_api.connectors.teams import TeamsAdapter, TeamsProviderError, _GraphResponse
from projecta_api.connectors.teams_auth import TeamsCredentialProvider
from projecta_api.identity.models import SessionRecord
from projecta_api.identity.oidc import IdentityError, IdentityService, _get_json
from projecta_api.identity.repository import InMemoryIdentityRepository
from projecta_api.operational.ports import InstallationRecord
from projecta_api.secrets.approle import FileAppRoleTokenProvider
from projecta_api.secrets.openbao import (
    InMemoryOpenBaoTransport,
    OpenBaoSecretError,
    OpenBaoSecretStore,
)


def _settings() -> Settings:
    return Settings(
        runtime_mode="production",
        oidc_issuer_url="https://auth.example.com/realms/projecta",
        oidc_client_id="projecta-web",
        oidc_redirect_uri="https://projecta.example.com/auth/callback",
        oidc_audience="projecta-web",
        identity_database_url="postgresql+psycopg://unused/unused",
    )


def _scope(revision: int = 1) -> SecretScope:
    return SecretScope("project-1", "installation-1", "teams", "tenant-1", revision)


def _installation(reference: str, revision: int = 1) -> InstallationRecord:
    now = datetime.now(UTC)
    return InstallationRecord(
        "installation-1", "project-1", "teams", {"providerTenant": "tenant-1"},
        reference, True, revision, now, now,
    )


def test_identity_stale_session_and_membership_removal_fail_closed() -> None:
    repository = InMemoryIdentityRepository()
    repository.save_session(
        SessionRecord("session-1", "subject-1", "actor-1", None,
                      datetime.now(UTC) + timedelta(minutes=5), datetime.now(UTC), None, "csrf", 1)
    )
    repository.replace_membership("subject-1", "project-1", ("project-reader",))
    service = IdentityService(_settings(), repository)
    assert service.principal("session-1", "project-1").project_id == "project-1"
    repository.remove_membership("subject-1", "project-1")
    with pytest.raises(IdentityError, match="PROJECT_FORBIDDEN"):
        service.principal("session-1", "project-1")


@pytest.mark.asyncio
async def test_keycloak_unavailability_is_a_bounded_identity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unavailable(_url: str) -> dict[str, object]:
        raise IdentityError("OIDC_PROVIDER_UNAVAILABLE", 503)

    monkeypatch.setattr("projecta_api.identity.oidc._get_json", unavailable)
    with pytest.raises(IdentityError, match="OIDC_PROVIDER_UNAVAILABLE") as error:
        await _get_json("https://auth.example.com/realms/projecta/.well-known/openid-configuration")
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_openbao_sealed_denied_and_rotation_race_are_bounded() -> None:
    transport = InMemoryOpenBaoTransport()
    store = OpenBaoSecretStore(transport, cache_ttl_seconds=0)
    first = store.create_scoped(_scope(), SecretStr("one"))
    policy = ConnectorSecretPolicy(store)
    assert policy.resolve_for_installation("project-1", _installation(first.reference)).get_secret_value() == "one"
    transport.seal()
    with pytest.raises(ConnectorSecretError, match="SECRET_SEALED"):
        policy.resolve_for_installation("project-1", _installation(first.reference))
    transport.unauthorized()
    with pytest.raises(ConnectorSecretError, match="SECRET_UNAUTHORIZED"):
        policy.resolve_for_installation("project-1", _installation(first.reference))
    transport.unseal()

    async def rotate(value: str):
        return await asyncio.to_thread(store.rotate_scoped, _scope(), first.reference, SecretStr(value))

    versions = await asyncio.gather(rotate("two"), rotate("three"))
    assert sorted(item.version for item in versions) == [2, 3]
    assert store.resolve_scoped(_scope(), first.reference).version == 3


def test_expired_workload_token_requires_reauthentication(tmp_path) -> None:
    role = tmp_path / "role"
    secret = tmp_path / "secret"
    role.write_text("role", encoding="utf-8")
    secret.write_text("secret", encoding="utf-8")

    class Login:
        def login(self, role_id: str, secret_id: str) -> tuple[str, int]:
            return "token", 60

        def renew(self, token: str) -> tuple[str, int]:
            return "renewed", 60

    provider = FileAppRoleTokenProvider(role, secret, Login())
    assert provider() == "token"
    provider._token = replace(provider._token, expires_at=datetime.now(UTC) - timedelta(seconds=1), max_expires_at=datetime.now(UTC) - timedelta(seconds=1))  # type: ignore[arg-type]
    with pytest.raises(OpenBaoSecretError, match="UNAUTHORIZED"):
        provider()


class _CredentialExchange:
    async def exchange(self, credential: object, deadline: datetime) -> tuple[str, int]:
        return "token", 120


class _TeamsGraph:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    async def get(self, path: str, token: str, params: object, deadline: datetime) -> _GraphResponse:
        return _GraphResponse(200, self.body, {})


def _teams_adapter(body: dict[str, object]) -> tuple[TeamsAdapter, object]:
    transport = InMemoryOpenBaoTransport()
    store = OpenBaoSecretStore(transport)
    scope = _scope()
    snapshot = store.create_scoped(scope, SecretStr(json.dumps({"tenantId": "tenant-1", "clientId": "client-1", "certificatePem": "cert", "privateKeyPem": "key"})))
    config = {
        "tenantId": "tenant-1", "teamId": "team-1", "channelId": "channel-1",
        "secretReference": snapshot.reference, "credentialRevision": 1,
    }
    from projecta_api.connectors.contracts import PullEventsCommand
    command = PullEventsCommand(
        installationId="installation-1", projectId="project-1", fixtureReference="fixture://teams/installation-1",
        deadline=datetime.now(UTC) + timedelta(seconds=30), correlationId="request-1", operationId="op-1",
        capability="inbound-import", installationRevision=1, providerConfig=config,
    )
    return TeamsAdapter(TeamsCredentialProvider(store, _CredentialExchange()), _TeamsGraph(body)), command


@pytest.mark.asyncio
async def test_teams_hostile_html_is_stripped_and_deleted_message_is_bounded() -> None:
    adapter, command = _teams_adapter({"value": [{
        "id": "message-1", "createdDateTime": "2026-08-13T00:00:00Z", "lastModifiedDateTime": "2026-08-13T00:00:00Z",
        "deletedDateTime": "2026-08-13T00:01:00Z", "body": {"content": "<script>alert(1)</script><p>safe</p>"},
    }]})
    token = await adapter._credentials.get_token(SecretScope("project-1", "installation-1", "teams", "tenant-1", 1), command.provider_config["secretReference"], command.deadline)  # type: ignore[index]
    assert token == "token"
    result = await adapter.pull_events(command)
    assert result.outcome == "succeeded", result.failure_code
    assert b"script" not in result.events[0].content_bytes
    assert len(result.events[0].content_bytes) <= 1024 * 1024


@pytest.mark.asyncio
async def test_teams_process_interruption_does_not_become_success() -> None:
    adapter, command = _teams_adapter({"value": []})

    class InterruptedGraph(_TeamsGraph):
        async def get(self, path: str, token: str, params: object, deadline: datetime) -> _GraphResponse:
            raise asyncio.CancelledError()

    adapter._graph = InterruptedGraph({})
    with pytest.raises(asyncio.CancelledError):
        await adapter.pull_events(command)


@pytest.mark.asyncio
async def test_two_project_scopes_remain_isolated_under_concurrent_resolution() -> None:
    transport = InMemoryOpenBaoTransport()
    store = OpenBaoSecretStore(transport, cache_ttl_seconds=0)
    project_one = SecretScope("project-one", "installation-1", "teams", "tenant-one", 1)
    project_two = SecretScope("project-two", "installation-1", "teams", "tenant-two", 1)
    first = store.create_scoped(project_one, SecretStr("one"))
    second = store.create_scoped(project_two, SecretStr("two"))
    values = await asyncio.gather(
        asyncio.to_thread(store.resolve_scoped, project_one, first.reference),
        asyncio.to_thread(store.resolve_scoped, project_two, second.reference),
    )
    assert [item.secret.get_secret_value() for item in values] == ["one", "two"]
    with pytest.raises(OpenBaoSecretError, match="MISSING"):
        store.resolve_scoped(project_two, first.reference)


@pytest.mark.asyncio
async def test_graph_http_statuses_map_to_finite_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from projecta_api.connectors.teams import HttpTeamsGraphTransport

    class Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code
            self.headers: dict[str, str] = {}
            self.content = b'{"value":[]}'

        def json(self) -> dict[str, object]:
            return {"value": []}

    class Client:
        def __init__(self, response: Response) -> None:
            self.response = response

        async def __aenter__(self) -> "Client":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> Response:
            return self.response

    for status, expected in ((401, "CREDENTIAL_INVALID"), (403, "PERMISSION_DENIED"), (429, "RATE_LIMITED")):
        monkeypatch.setattr(
            "projecta_api.connectors.teams.httpx.AsyncClient",
            lambda status=status, **kwargs: Client(Response(status)),
        )
        with pytest.raises(TeamsProviderError, match=expected):
            await HttpTeamsGraphTransport().get(
                "/v1.0/teams/team-1/channels/channel-1/messages", "token",
                {"$top": "50"}, datetime.now(UTC) + timedelta(seconds=5),
            )
