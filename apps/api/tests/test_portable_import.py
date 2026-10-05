from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse

from projecta_api.export_fence import ProjectWriteFence, ProjectWriteFenceMiddleware
from projecta_api.portable_import import (
    PortableImportFailure,
    _check_no_secret_fields,
    _validate_archive_references,
)


@pytest.mark.asyncio
async def test_import_fence_drains_streaming_reads_before_publication() -> None:
    fence = ProjectWriteFence()
    app = FastAPI()
    app.add_middleware(ProjectWriteFenceMiddleware, fence=fence)
    stream_started = asyncio.Event()
    release_stream = asyncio.Event()
    import_started = asyncio.Event()
    release_import = asyncio.Event()

    @app.get("/v1/projects/stream")
    async def stream_project() -> StreamingResponse:
        async def content():
            stream_started.set()
            yield b"before"
            await release_stream.wait()
            yield b"after"

        return StreamingResponse(content())

    async def import_project() -> None:
        async with fence.maintenance_epoch():
            import_started.set()
            await release_import.wait()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        read = asyncio.create_task(client.get("/v1/projects/stream"))
        await asyncio.wait_for(stream_started.wait(), timeout=1)
        applying = asyncio.create_task(import_project())
        await asyncio.sleep(0)

        assert not import_started.is_set()
        assert await fence.enter_read() is False
        assert await fence.enter_write() is False

        release_stream.set()
        response = await asyncio.wait_for(read, timeout=1)
        assert response.content == b"beforeafter"
        await asyncio.wait_for(import_started.wait(), timeout=1)
        assert await fence.enter_read() is False
        release_import.set()
        await applying

    assert await fence.enter_read() is True
    await fence.exit_read()


@pytest.mark.asyncio
async def test_recovery_required_fence_rejects_all_project_api_reads() -> None:
    fence = ProjectWriteFence()
    app = FastAPI()
    app.add_middleware(ProjectWriteFenceMiddleware, fence=fence)

    @app.get("/v1/projects")
    async def list_projects() -> dict[str, object]:
        return {"projects": []}

    await fence.require_recovery()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/v1/projects")

    assert response.status_code == 503
    assert response.json()["code"] == "IMPORT_RECOVERY_REQUIRED"


def test_import_rejects_unresolved_receipt_links() -> None:
    receipt_digest = "sha256:" + "a" * 64
    workflows = {
        "suggestionWorkflows": [{"latestReceiptDigest": receipt_digest}],
        "authoringCostEvents": [],
    }

    with pytest.raises(PortableImportFailure, match="IMPORT_PACKAGE_INVALID"):
        _validate_archive_references(workflows, ())

    with pytest.raises(PortableImportFailure, match="IMPORT_PACKAGE_INVALID"):
        _validate_archive_references(
            {
                "suggestionWorkflows": [],
                "authoringCostEvents": [{"receiptDigest": receipt_digest}],
            },
            (),
        )

    _validate_archive_references(
        {
            "suggestionWorkflows": [{"latestReceiptDigest": receipt_digest}],
            "authoringCostEvents": [{"receiptDigest": receipt_digest}],
        },
        ({"receiptDigest": receipt_digest},),
    )


def test_import_rejects_nested_secret_fields_and_normalizes_names() -> None:
    with pytest.raises(PortableImportFailure, match="IMPORT_PACKAGE_INVALID"):
        _check_no_secret_fields({"proposal": [{"provider_token": "excluded"}]})

    with pytest.raises(PortableImportFailure, match="IMPORT_PACKAGE_INVALID"):
        _check_no_secret_fields({"connector": {"AUTHORIZATION": "excluded"}})

    _check_no_secret_fields(
        {"receipt": {"authorizationDigest": "sha256:" + "b" * 64}, "attemptTokenCount": 2}
    )


def test_import_maps_corrupt_deflate_payload_to_finite_error(tmp_path) -> None:
    """A mid-archive byte flip that breaks deflate decoding must fail closed finite."""
    import hashlib
    import zipfile

    from projecta_api.portable_import import _validate_archive

    source = tmp_path / "source.projecta"
    with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b'{"portableContract": "projecta-portable.v1"}')
        archive.writestr("payload/semantic/project.trig", b"a" * 4096)
    raw = bytearray(source.read_bytes())
    raw[100] ^= 0xFF
    raw = bytes(raw)
    target_dir = tmp_path / "staged"
    target_dir.mkdir()
    target = target_dir / "package.projecta"
    target.write_bytes(raw)
    with pytest.raises(PortableImportFailure, match="IMPORT_PACKAGE_INVALID"):
        _validate_archive("probe", target_dir, target, hashlib.sha256(raw).hexdigest(), len(raw))
