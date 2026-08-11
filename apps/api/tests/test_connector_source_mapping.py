"""E-task tests for connector source mapping and Semantic Core input bounds."""

from datetime import UTC, datetime

import pytest

from projecta_api.connectors.contracts import RawEventCandidate
from projecta_api.connectors.event_validation import validate_and_canonicalize
from projecta_api.connectors.semantic_source import ConnectorSemanticSourceCommitter
from projecta_api.connectors.source_mapping import ConnectorSourceMappingError, map_event_to_capture
from projecta_api.context import TrustedRequestContext
from projecta_api.evidence.ports import EvidenceGetRequest, EvidenceMetadata, EvidenceReceipt


def _event(content: bytes):
    candidate = RawEventCandidate(
        eventId="evt-source-001",
        eventType="source.created",
        externalReference="fixture://project-a/message-001",
        occurredAt=datetime(2026, 8, 10, tzinfo=UTC),
        contentType="application/json",
        contentBytes=content,
    )
    return validate_and_canonicalize(
        candidate,
        project_id="project-a",
        installation_id="install-a",
        connector_type="json-mock",
        evidence_reference="ev_" + "a" * 22,
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )


def test_mapping_preserves_connector_source_kind_hash_and_exact_offsets() -> None:
    content = b'{"title":"Imported","items":[{"type":"requirement","text":"Ship it"},{"type":"risk","text":"Needs review"}]}'
    request = map_event_to_capture(_event(content), content, actor_id="actor-a")

    assert request.source_kind == "connector"
    assert request.source_content_hash == _event(content).content.content_hash
    assert request.raw_text == "Ship it\nNeeds review"
    assert [(item.start_offset, item.end_offset, item.text) for item in request.segments] == [
        (0, 7, "Ship it"),
        (8, 20, "Needs review"),
    ]


@pytest.mark.parametrize(
    "payload, code",
    [
        (b"not-json", "CONNECTOR_SOURCE_INVALID"),
        (b'{"title":"Imported","items":[]}', "CONNECTOR_SOURCE_ABSTAINED"),
        (b'{"title":"Imported","items":[{"type":"assertion","text":"No"}]}', "CONNECTOR_SOURCE_ABSTAINED"),
    ],
)
def test_mapping_abstains_from_malformed_or_unsupported_source_content(payload: bytes, code: str) -> None:
    with pytest.raises(ConnectorSourceMappingError, match=code):
        valid = b'{"title":"Imported","items":[{"type":"task","text":"Ship it"}]}'
        map_event_to_capture(_event(valid), payload, actor_id="actor-a")


class _Evidence:
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def get(self, request: EvidenceGetRequest, *, max_bytes: int):
        assert request.project_scope == "project-a"
        assert max_bytes == 1024 * 1024

        async def chunks():
            yield self.content

        return (
            EvidenceMetadata(
                evidence_reference="ev_" + "a" * 22,
                project_scope="project-a",
                sha256="0" * 64,
                size_bytes=len(self.content),
                content_type="application/json",
                created_at=datetime(2026, 8, 10, tzinfo=UTC),
                retention_class="connector-default",
                retain_until=None,
                source_reference="fixture://project-a/message-001",
            ),
            chunks(),
        )


class _SemanticClient:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def capture(self, context, key, request):
        self.calls.append((context, key, request))


@pytest.mark.asyncio
async def test_semantic_committer_reuses_capture_boundary_with_server_context() -> None:
    content = b'{"title":"Imported","items":[{"type":"task","text":"Ship it"}]}'
    client = _SemanticClient()
    committer = ConnectorSemanticSourceCommitter(
        client, _Evidence(content), TrustedRequestContext("project-a", "actor-a", "req-a")
    )
    await committer.commit_source(
        _event(content),
        EvidenceReceipt("ev_" + "a" * 22, "0" * 64, len(content), "application/json", False),
    )

    context, key, request = client.calls[0]
    assert context.project_id == "project-a"
    assert key.startswith("connector-evt-source-001-")
    assert request.source_kind == "connector"
