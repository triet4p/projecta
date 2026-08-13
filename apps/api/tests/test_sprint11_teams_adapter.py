"""Replay and negative tests for the Sprint 11 Teams adapter boundary."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr

from projecta_api.configuration.ports import SecretScope
from projecta_api.connectors.contracts import PullEventsCommand, RawEventCandidate
from projecta_api.connectors.event_validation import validate_and_canonicalize
from projecta_api.connectors.source_mapping import map_event_to_capture
from projecta_api.connectors.teams import (
    TeamsAdapter,
    TeamsInstallationConfig,
    TeamsProviderError,
    _GraphResponse,
    _validate_next_link,
)
from projecta_api.connectors.teams_auth import TeamsCredentialProvider
from projecta_api.secrets.openbao import InMemoryOpenBaoTransport, OpenBaoSecretStore

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _config() -> TeamsInstallationConfig:
    return TeamsInstallationConfig(
        tenantId="tenant-1",
        teamId="team-1",
        channelId="channel-1",
        secretReference="secret_1234567890",
        credentialRevision=1,
    )


def _command(config: TeamsInstallationConfig) -> PullEventsCommand:
    return PullEventsCommand(
        installationId="install-1",
        projectId="project-1",
        fixtureReference="fixture://teams/install-1",
        deadline=datetime.now(UTC) + timedelta(seconds=30),
        correlationId="request-1",
        operationId="operation-1",
        capability="inbound-import",
        installationRevision=1,
        providerConfig=config.model_dump(by_alias=True),
    )


class _Exchange:
    def __init__(self) -> None:
        self.calls = 0

    async def exchange(self, credential, deadline):
        self.calls += 1
        return "graph-access-token", 300


class _Graph:
    def __init__(self, root_body, reply_body) -> None:
        self.root_body = root_body
        self.reply_body = reply_body
        self.paths: list[str] = []

    async def get(self, path, token, params, deadline):
        assert token == "graph-access-token"
        self.paths.append(path)
        body = self.reply_body if path.endswith("/replies") else self.root_body
        return _GraphResponse(200, body, {})


def _adapter(root_body, reply_body):
    store = OpenBaoSecretStore(InMemoryOpenBaoTransport())
    scope = SecretScope("project-1", "install-1", "teams", "tenant-1", 1)
    snapshot = store.create_scoped(
        scope,
        SecretStr(
            json.dumps(
                {
                    "tenantId": "tenant-1",
                    "clientId": "client-1",
                    "certificatePem": "certificate-placeholder",
                    "privateKeyPem": "private-key-placeholder",
                }
            )
        ),
    )
    exchange = _Exchange()
    graph = _Graph(root_body, reply_body)
    config = _config().model_copy(update={"secret_reference": snapshot.reference})
    return TeamsAdapter(TeamsCredentialProvider(store, exchange), graph), exchange, graph, config


def _root_body(next_link=None):
    body = {
        "value": [
            {
                "id": "root-1",
                "createdDateTime": "2026-08-12T11:00:00Z",
                "lastModifiedDateTime": "2026-08-12T11:00:00Z",
                "from": {"user": {"id": "user-1", "displayName": "Reviewer"}},
                "body": {"contentType": "html", "content": "<p>Hello <b>Teams</b></p>"},
            }
        ]
    }
    if next_link is not None:
        body["@odata.nextLink"] = next_link
    return body


def _reply_body():
    return {
        "value": [
            {
                "id": "reply-1",
                "createdDateTime": "2026-08-12T11:01:00Z",
                "lastModifiedDateTime": "2026-08-12T11:02:00Z",
                "from": {"user": {"id": "user-2", "displayName": "Responder"}},
                "body": {"contentType": "html", "content": "<div>Reply</div>"},
            }
        ]
    }


@pytest.mark.asyncio
async def test_teams_replay_normalizes_root_and_reply_without_provider_ids() -> None:
    adapter, exchange, graph, config = _adapter(_root_body(), _reply_body())
    result = await adapter.pull_events(_command(config))

    assert result.outcome == "succeeded"
    assert len(result.events) == 2
    assert result.events[0].event_id.startswith("evt-")
    assert result.events[0].external_reference.startswith("teams://message/")
    assert "root-1" not in result.events[0].external_reference
    assert b"Hello Teams" in result.events[0].content_bytes
    assert b"<p>" not in result.events[0].content_bytes
    assert "root-1" not in result.events[1].content_bytes.decode()
    assert any(path.endswith("/messages/root-1/replies") for path in graph.paths)
    assert exchange.calls == 1


@pytest.mark.asyncio
async def test_root_next_link_is_validated_and_reported_as_truncated() -> None:
    next_link = "https://graph.microsoft.com/v1.0/teams/team-1/channels/channel-1/messages?$skiptoken=next"
    adapter, _, _, config = _adapter(_root_body(next_link), {"value": []})
    result = await adapter.pull_events(_command(config))
    assert result.outcome == "truncated"
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_invalid_next_link_and_provider_failures_are_finite() -> None:
    bad_link = "https://evil.example/v1.0/teams/team-1/channels/channel-1/messages"
    adapter, _, _, config = _adapter(_root_body(bad_link), {"value": []})
    malformed = await adapter.pull_events(_command(config))
    assert malformed.outcome == "malformed-output"
    assert malformed.failure_code == "ADAPTER_OUTPUT_INVALID"

    class _DeniedGraph(_Graph):
        async def get(self, path, token, params, deadline):
            raise TeamsProviderError("PERMISSION_DENIED")

    denied_adapter, _, _, config = _adapter(_root_body(), _reply_body())
    denied_adapter._graph = _DeniedGraph({}, {})
    denied = await denied_adapter.pull_events(_command(config))
    assert denied.outcome == "unavailable"
    assert denied.failure_code == "ADAPTER_PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_cursor_filters_replayed_watermark_and_edit_creates_new_event_identity() -> None:
    adapter, _, _, config = _adapter(_root_body(), {"value": []})
    first = await adapter.pull_events(_command(config))
    assert first.next_cursor is not None
    replay_command = _command(config).model_copy(update={"cursor": first.next_cursor})
    replay = await adapter.pull_events(replay_command)
    assert replay.outcome == "empty"

    edited_root = _root_body()
    edited_root["value"][0]["lastModifiedDateTime"] = "2026-08-12T12:00:00Z"
    edited_adapter, _, _, edited_config = _adapter(edited_root, {"value": []})
    edited = await edited_adapter.pull_events(_command(edited_config))
    assert edited.events[0].event_id != first.events[0].event_id


@pytest.mark.asyncio
async def test_cursor_still_discovers_a_new_reply_on_an_old_root() -> None:
    initial_adapter, _, _, config = _adapter(_root_body(), {"value": []})
    initial = await initial_adapter.pull_events(_command(config))
    assert initial.next_cursor is not None

    reply_adapter, _, _, reply_config = _adapter(_root_body(), _reply_body())
    command = _command(reply_config).model_copy(update={"cursor": initial.next_cursor})
    result = await reply_adapter.pull_events(command)
    assert result.outcome == "succeeded"
    assert len(result.events) == 1
    assert b"Reply" in result.events[0].content_bytes


@pytest.mark.asyncio
async def test_large_content_is_complete_or_truthfully_truncated() -> None:
    within_limit = _root_body()
    within_limit["value"][0]["body"]["content"] = "x" * 20_000
    adapter, _, _, config = _adapter(within_limit, {"value": []})
    complete = await adapter.pull_events(_command(config))
    assert complete.outcome == "succeeded"
    assert len(json.loads(complete.events[0].content_bytes)["bodyText"]) == 20_000

    oversized = _root_body()
    oversized["value"][0]["body"]["content"] = "x" * (1024 * 1024 + 100)
    oversized_adapter, _, _, oversized_config = _adapter(oversized, {"value": []})
    limited = await oversized_adapter.pull_events(_command(oversized_config))
    assert limited.outcome == "truncated"
    assert limited.events == ()


def test_absolute_graph_next_link_is_normalized_to_the_fixed_relative_scope() -> None:
    config = _config()
    path = "/v1.0/teams/team-1/channels/channel-1/messages/root-1/replies"
    value = f"https://graph.microsoft.com{path}?$skiptoken=next"
    assert _validate_next_link(value, config, path) == f"{path}?$skiptoken=next"


def test_teams_installation_configuration_is_internal_and_finite() -> None:
    config = _config()
    adapter, _, _, _ = _adapter(_root_body(), _reply_body())
    assert config.model_dump(by_alias=True)["tenantId"] == "tenant-1"
    assert "ChannelMessage.Read.All" not in config.capabilities
    with pytest.raises(ValueError):
        TeamsInstallationConfig(
            tenantId="tenant-1",
            teamId="team-1",
            channelId="channel-1",
            secretReference="bad-reference",
        )
    assert adapter.descriptor().connector_type == "teams"


def test_teams_events_reuse_the_existing_semantic_capture_boundary() -> None:
    candidate = RawEventCandidate(
        eventId="evt-teams-001",
        eventType="source.created",
        externalReference="teams://message/abc",
        occurredAt=NOW,
        contentType="application/json",
        contentBytes=b'{"bodyText":"Hello Teams","deleted":false}',
    )
    event = validate_and_canonicalize(
        candidate,
        project_id="project-1",
        installation_id="install-1",
        connector_type="teams",
        evidence_reference="ev_" + "a" * 22,
        now=NOW,
    )
    mapped = map_event_to_capture(event, candidate.content_bytes, actor_id="actor-1")
    assert mapped.source_kind == "connector"
    assert mapped.raw_text == "Hello Teams"
    assert mapped.segments[0].type == "progress-update"
