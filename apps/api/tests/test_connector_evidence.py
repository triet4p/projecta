"""Safety and lifecycle tests for the local evidence adapter."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import pytest

from projecta_api.evidence import (
    EvidenceError,
    EvidenceGetRequest,
    EvidenceHeadRequest,
    EvidencePutRequest,
    LocalEvidenceStore,
)


async def chunks(value: bytes) -> AsyncIterator[bytes]:
    yield value[:2]
    yield value[2:]


def request(
    project: str, payload: bytes, *, content_type: str = "application/json"
) -> EvidencePutRequest:
    return EvidencePutRequest(
        project_scope=project,
        content_type=content_type,
        declared_size=len(payload),
        declared_sha256=hashlib.sha256(payload).hexdigest(),
        source_reference="event-1",
    )


@pytest.mark.asyncio
async def test_put_get_head_and_same_content_are_idempotent(tmp_path: Path) -> None:
    store = LocalEvidenceStore(tmp_path)
    payload = b'{"bounded":true}'
    first = await store.put(request("project-a", payload), chunks(payload))
    second = await store.put(request("project-a", payload), chunks(payload))

    assert first.idempotent_reuse is False
    assert second.idempotent_reuse is True
    assert second.evidence_reference == first.evidence_reference
    metadata = await store.head(EvidenceHeadRequest("project-a", first.evidence_reference))
    _, stream = await store.get(
        EvidenceGetRequest("project-a", first.evidence_reference), max_bytes=len(payload)
    )
    assert metadata.sha256 == first.sha256
    assert b"".join([part async for part in stream]) == payload


@pytest.mark.asyncio
async def test_concurrent_puts_share_one_reference_and_direct_index(tmp_path: Path) -> None:
    store = LocalEvidenceStore(tmp_path)
    payload = b'{"concurrent":true}'
    first, second = await asyncio.gather(
        store.put(request("project-a", payload), chunks(payload)),
        store.put(request("project-a", payload), chunks(payload)),
    )

    assert first.evidence_reference == second.evidence_reference
    assert sorted((first.idempotent_reuse, second.idempotent_reuse)) == [False, True]
    reference_files = list((tmp_path / "references" / "project-a").glob("*.json"))
    assert len(reference_files) == 1
    assert reference_files[0].stem == first.evidence_reference


@pytest.mark.asyncio
async def test_digest_media_size_and_scope_fail_closed(tmp_path: Path) -> None:
    store = LocalEvidenceStore(tmp_path, max_bytes=8)
    payload = b"payload"
    bad_digest = request("project-a", payload)
    bad_digest = replace(bad_digest, declared_sha256="0" * 64)
    with pytest.raises(EvidenceError, match="EVIDENCE_DIGEST_MISMATCH"):
        await store.put(bad_digest, chunks(payload))
    with pytest.raises(EvidenceError, match="EVIDENCE_CONTENT_TYPE_UNSUPPORTED"):
        await store.put(
            request("project-a", payload, content_type="application/octet-stream"), chunks(payload)
        )
    with pytest.raises(EvidenceError, match="EVIDENCE_SIZE_EXCEEDED"):
        await store.put(request("project-a", b"123456789"), chunks(b"123456789"))

    valid = await store.put(request("project-a", payload), chunks(payload))
    with pytest.raises(EvidenceError, match="EVIDENCE_NOT_FOUND"):
        await store.head(EvidenceHeadRequest("project-b", valid.evidence_reference))
    with pytest.raises(EvidenceError, match="EVIDENCE_REFERENCE_INVALID"):
        await store.head(EvidenceHeadRequest("project-a", "../metadata.json"))


@pytest.mark.asyncio
async def test_interrupted_write_leaves_no_visible_object(tmp_path: Path) -> None:
    store = LocalEvidenceStore(tmp_path)

    async def interrupted() -> AsyncIterator[bytes]:
        yield b"partial"
        raise RuntimeError("simulated interruption")

    with pytest.raises(EvidenceError, match="EVIDENCE_WRITE_INTERRUPTED"):
        await store.put(request("project-a", b"partial"), interrupted())
    assert await asyncio.to_thread(lambda: list(tmp_path.rglob("metadata.json"))) == []
    assert await asyncio.to_thread(lambda: list(tmp_path.rglob("content"))) == []


@pytest.mark.asyncio
async def test_cancellation_and_bounded_read_are_typed(tmp_path: Path) -> None:
    store = LocalEvidenceStore(tmp_path)
    payload = b"1234"
    receipt = await store.put(request("project-a", payload), chunks(payload))
    with pytest.raises(EvidenceError, match="EVIDENCE_READ_LIMIT_EXCEEDED"):
        await store.get(EvidenceGetRequest("project-a", receipt.evidence_reference), max_bytes=3)
    cancellation = asyncio.Event()
    cancellation.set()
    with pytest.raises(EvidenceError, match="EVIDENCE_CANCELLED"):
        await store.get(
            EvidenceGetRequest("project-a", receipt.evidence_reference),
            max_bytes=len(payload),
            cancellation=cancellation,
        )


@pytest.mark.asyncio
async def test_get_recomputes_integrity_and_source_reference_is_safe(tmp_path: Path) -> None:
    store = LocalEvidenceStore(tmp_path)
    payload = b"1234"
    receipt = await store.put(request("project-a", payload), chunks(payload))
    object_path = (
        tmp_path / "objects" / "project-a" / receipt.sha256[:2] / receipt.sha256 / "content"
    )
    object_path.write_bytes(b"4321")

    _, stream = await store.get(
        EvidenceGetRequest("project-a", receipt.evidence_reference), max_bytes=len(payload)
    )
    with pytest.raises(EvidenceError, match="EVIDENCE_INTEGRITY_FAILED"):
        b"".join([part async for part in stream])

    unsafe = replace(request("project-a", payload), source_reference="../secret")
    with pytest.raises(EvidenceError, match="EVIDENCE_METADATA_INVALID"):
        await store.put(unsafe, chunks(payload))
