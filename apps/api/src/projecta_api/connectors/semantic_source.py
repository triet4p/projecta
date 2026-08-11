"""Semantic Core source committer for connector evidence."""

from __future__ import annotations

from collections.abc import AsyncIterator

from projecta_api.connectors.contracts import CanonicalEvent
from projecta_api.connectors.orchestration import SourceCommitter
from projecta_api.connectors.source_mapping import map_event_to_capture
from projecta_api.context import TrustedRequestContext
from projecta_api.evidence.ports import EvidenceGetRequest, EvidenceReceipt, EvidenceStore
from projecta_api.semantic_core import SemanticCoreClient


class ConnectorSemanticSourceCommitter(SourceCommitter):
    """Reuse the released capture operation; no direct RDF or assertion write."""

    def __init__(self, client: SemanticCoreClient, evidence: EvidenceStore, context: TrustedRequestContext) -> None:
        self._client = client
        self._evidence = evidence
        self._context = context

    async def commit_source(self, event: CanonicalEvent, evidence: EvidenceReceipt) -> None:
        metadata, stream = await self._evidence.get(
            EvidenceGetRequest(self._context.project_id, evidence.evidence_reference),
            max_bytes=1024 * 1024,
        )
        content = await _read_bounded(stream, metadata.size_bytes)
        capture = map_event_to_capture(event, content, actor_id=self._context.actor_id)
        key = f"connector-{event.event_id}-{event.canonical_body_hash[7:23]}"
        await self._client.capture(self._context, key, capture)


async def _read_bounded(stream: AsyncIterator[bytes], expected_size: int) -> bytes:
    chunks: list[bytes] = []
    observed = 0
    async for chunk in stream:
        observed += len(chunk)
        if observed > 1024 * 1024:
            raise ValueError("CONNECTOR_SOURCE_LIMIT_EXCEEDED")
        chunks.append(chunk)
    if observed != expected_size:
        raise ValueError("CONNECTOR_SOURCE_SIZE_MISMATCH")
    return b"".join(chunks)
