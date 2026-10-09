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
    _validate_producer,
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


@pytest.mark.local_contract
def test_import_accepts_pre_purge_producer_head_without_shape_change() -> None:
    """Pre-purge (0011-stamped) producer stays importable: 0012 adds only the purge helper."""
    from projecta_api.extraction.correction_burden import CORRECTION_BURDEN_CONTRACT_VERSION
    from projecta_api.extraction.review_receipts import REVIEW_RECEIPT_CONTRACT_VERSION
    from projecta_api.portable_export import ontology_assets

    producer: dict[str, object] = {
        "projectaVersion": "0.7.0",
        "apiVersion": "0.7.0",
        "webVersion": "0.7.0",
        "nativeRuntime": {
            "python": "3.12.10",
            "java": "21.0.12.1+1",
            "fuseki": "6.2.0",
            "postgresql": "16.15",
            "semanticCore": {"javalin": "7.2.2", "jena": "6.2.0"},
        },
        "postgresAlembicHead": "0011_review_receipts_append_only",
        "sqliteSchemaVersions": [1, 2, 3],
        "connectorContract": "connector-contract.v1",
        "reviewReceiptContract": REVIEW_RECEIPT_CONTRACT_VERSION,
        "correctionBurdenContract": CORRECTION_BURDEN_CONTRACT_VERSION,
        "ontologyAssets": ontology_assets(),
    }
    # Current-database producer passes unchanged (no exception).
    _validate_producer({**producer, "postgresAlembicHead": "0012_project_purge_exception"})
    # Pre-purge producer passes through the bounded compatibility branch.
    _validate_producer(producer)
    # Any other head still fails closed.
    with pytest.raises(PortableImportFailure, match="IMPORT_UNSUPPORTED_VERSION"):
        _validate_producer({**producer, "postgresAlembicHead": "0009_review_decision_receipts"})

def test_import_after_empty_catalog_repoints_serving_primary() -> None:
    """Fresh import on the persisted empty catalog re-points the serving primary.

    Regression: last-project deletion persists ``projects: []`` with the stale
    first-run header; the next fresh import must repair the header so the
    launcher ``entries[0] == header`` invariant holds again across restart.
    """
    from projecta_api.portable_import import _append_project

    empty = {
        "formatVersion": 1,
        "projectId": "my-projecta-workspace",
        "projectName": "My Projecta Workspace",
        "actorId": "local-operator",
        "projects": [],
    }
    repaired = _append_project(empty, "fresh-project", "Fresh Project", False)
    assert repaired["projects"] == [
        {"projectId": "fresh-project", "projectName": "Fresh Project"}
    ]
    assert repaired["projectId"] == "fresh-project"
    assert repaired["projectName"] == "Fresh Project"


def test_import_on_nonempty_catalog_keeps_serving_primary() -> None:
    """Ordinary imports never move the serving primary header."""
    from projecta_api.portable_import import _append_project

    registry = {
        "formatVersion": 1,
        "projectId": "my-projecta-workspace",
        "projectName": "My Projecta Workspace",
        "actorId": "local-operator",
        "projects": [
            {"projectId": "my-projecta-workspace", "projectName": "My Projecta Workspace"}
        ],
    }
    updated = _append_project(registry, "second-project", "Second Project", False)
    assert updated["projectId"] == "my-projecta-workspace"
    assert [item["projectId"] for item in updated["projects"]] == [
        "my-projecta-workspace",
        "second-project",
    ]


def test_successful_publication_requests_no_restart(tmp_path) -> None:
    """A clean publication exposes no restart affordance on the live contract."""
    from projecta_api.portable_import import ProjectPortableImportService

    assert not hasattr(ProjectPortableImportService, "_request_runtime_restart")
    assert not hasattr(ProjectPortableImportService, "_request_recovery_restart")
    assert not (tmp_path / "state" / "import-restart.json").exists()
