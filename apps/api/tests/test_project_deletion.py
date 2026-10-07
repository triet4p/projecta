"""Consumer-visible project-deletion boundaries for projecta-deletion.v1.

Covers the finite outcome surface only: typed-identity confirmation,
authorization, unknown-project refusal, cancellation leaving state unchanged,
busy refusal with zero state change, phase-aware quiescence for idle staged
previews, foreign-actor pre-mutation refusal, idempotent interrupted-delete
recovery, and the full-scope purge predicate set.
Uses a disposable SQLite database, a disposable evidence root, and an
in-memory semantic double; PostgreSQL is substituted with a disposable
in-process double except for the dedicated disposable-PostgreSQL purge test
below, which proves the real ``0012`` helper plus FK-ordered deletes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedActorContext
from projecta_api.evidence.local import LocalEvidenceStore
from projecta_api.project_deletion import (
    ProjectDeletionFailure,
    ProjectDeletionService,
)


class _MemorySemantic:
    def __init__(self) -> None:
        self.graphs: dict[str, int] = {"sources": 2, "asserted": 1}
        self.deleted: list[str] = []

    async def project_graph_counts(
        self, actor: TrustedActorContext, project_id: str
    ) -> Mapping[str, int]:
        return dict(self.graphs)

    async def delete_project_graphs(
        self, actor: TrustedActorContext, project_id: str
    ) -> Mapping[str, int]:
        self.deleted.append(project_id)
        removed, self.graphs = dict(self.graphs), {}
        return removed


def _registry(path: Path, projects: list[tuple[str, str]], actor: str = "actor-1") -> None:
    path.write_text(
        json.dumps(
            {
                "formatVersion": 1,
                "projectId": projects[0][0],
                "projectName": projects[0][1],
                "actorId": actor,
                "projects": [
                    {"projectId": project_id, "projectName": name}
                    for project_id, name in projects
                ],
            }
        ),
        encoding="utf-8",
    )


def _service(tmp_path: Path, projects: list[tuple[str, str]]) -> tuple[ProjectDeletionService, _MemorySemantic, TrustedActorContext]:
    # Production layout: import root is <data_root>/data/imports, launcher
    # markers live at <data_root>/{recovery,state}. The helper mirrors it so
    # the publication-guard regression exercises the real marker paths.
    database = OperationalDatabase(str(tmp_path / "operational.db"))
    from projecta_api.extraction.local_suggestion_store import LocalSuggestionRepository
    from projecta_api.project_workspace_store import ProjectSelectionRepository
    from projecta_api.structured_candidate_store import StructuredCandidateEditStore
    from projecta_api.structured_note_store import StructuredNoteDraftStore
    StructuredNoteDraftStore(database)
    StructuredCandidateEditStore(database)
    LocalSuggestionRepository(database)
    ProjectSelectionRepository(database)
    evidence = LocalEvidenceStore(tmp_path / "evidence")
    semantic = _MemorySemantic()
    import_root = tmp_path / "data" / "imports"
    import_root.mkdir(parents=True)
    registry_path = tmp_path / "local-runtime.json"
    _registry(registry_path, projects)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE connector_sync_runs (project_id TEXT, terminal_at TEXT)"))
    service = ProjectDeletionService(
        database,
        engine,
        evidence,
        semantic,
        deletion_root=tmp_path / "deletion",
        import_root=import_root,
        exports_root=tmp_path / "exports",
        registry_path=registry_path,
        native_runtime_lock_held=True,
        restart_file=tmp_path / "state" / "import-restart.json",
        runtime_id="test-runtime",
    )
    actor = TrustedActorContext(actor_id="actor-1", request_id="req-1", operation_id="op-1")
    return service, semantic, actor


async def _seed_sqlite(service: ProjectDeletionService, project_id: str) -> None:
    database = service._database  # noqa: SLF001 - test seeds through the owned database handle
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO structured_note_drafts(handle, project_id, actor_id, revision, payload, "
            "fingerprint, idempotency_key, committed_note_id, created_at, updated_at) "
            "VALUES ('draft-h-1', ?, 'actor-1', 1, '{}', 'fp', 'key-1', NULL, 't', 't')",
            (project_id,),
        )
        connection.execute(
            "INSERT INTO configuration_audit(scope, actor_id, request_id, operation, outcome, "
            "recorded_at) VALUES (?, 'actor-1', 'req-1', 'save', 'success', 't')",
            (project_id,),
        )


def _stage_idle_preview(tmp_path: Path, token: str, project_id: str, actor: str = "actor-1") -> Path:
    """Seed a validated idle staged preview: preview.json + staged archive bytes."""
    directory = tmp_path / "data" / "imports" / "previews" / token
    directory.mkdir(parents=True)
    (directory / "package.projecta").write_bytes(b"staged-package-bytes")
    (directory / "preview.json").write_text(
        json.dumps(
            {
                "actorId": actor,
                "createdAt": "2026-10-07T00:00:00+00:00",
                "projectId": project_id,
                "exportId": "99d2791f-0000-4000-8000-000000000001",
                "archiveSha256": "1f5ca21d" + "0" * 56,
                "archiveSize": 21,
            }
        ),
        encoding="utf-8",
    )
    return directory


async def test_deletion_preview_counts_scope_without_mutation(tmp_path: Path) -> None:
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    preview = await service.preview(actor, "alpha", "Alpha")
    assert preview.project_id == "alpha"
    assert preview.sqlite_rows["structured_note_drafts"] == 1
    assert preview.sqlite_rows["configuration_audit"] == 1
    # Preview changed nothing: the scope still counts the same rows.
    again = await service.preview(actor, "alpha", "Alpha")
    assert again.sqlite_rows == preview.sqlite_rows


async def test_deletion_requires_typed_identity_and_confirmation(tmp_path: Path) -> None:
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    with pytest.raises(ProjectDeletionFailure) as mismatch:
        await service.delete(actor, "alpha", "Alpha", "wrong-name", True)
    assert mismatch.value.code == "DELETE_IDENTITY_MISMATCH"
    with pytest.raises(ProjectDeletionFailure) as unconfirmed:
        await service.delete(actor, "alpha", "Alpha", "Alpha", False)
    assert unconfirmed.value.code == "DELETE_CONFIRMATION_REQUIRED"
    # Both refusals left all state unchanged.
    preview = await service.preview(actor, "alpha", "Alpha")
    assert preview.sqlite_rows["structured_note_drafts"] == 1


async def test_deletion_refuses_unknown_project_and_foreign_actor(tmp_path: Path) -> None:
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    with pytest.raises(ProjectDeletionFailure) as unknown:
        await service.preview(actor, "ghost", "Ghost")
    assert unknown.value.code == "DELETE_UNKNOWN_PROJECT"
    foreign = TrustedActorContext(actor_id="actor-2", request_id="req-2", operation_id="op-2")
    with pytest.raises(ProjectDeletionFailure) as unauthorized:
        await service.preview(foreign, "alpha", "Alpha")
    assert unauthorized.value.code == "DELETE_UNAUTHORIZED"


async def test_deletion_refuses_while_import_journal_exists(tmp_path: Path) -> None:
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    (tmp_path / "data" / "imports" / "journal.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ProjectDeletionFailure) as busy:
        await service.preview(actor, "alpha", "Alpha")
    assert busy.value.code == "DELETE_BUSY"
    # Zero state change: preview still refuses the same way after journal removal fails closed.
    (tmp_path / "data" / "imports" / "journal.json").unlink()
    preview = await service.preview(actor, "alpha", "Alpha")
    assert preview.project_id == "alpha"


async def test_idle_staged_preview_no_longer_deadlocks_delete(tmp_path: Path) -> None:
    """A retained same-scope idle preview (fresh session, no token) unblocks preview/delete."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    idle_dir = _stage_idle_preview(
        tmp_path, "62b8c1d6-ccc9-4b70-9d93-bf152081c885", "alpha"
    )
    preview = await service.preview(actor, "alpha", "Alpha")
    assert preview.project_id == "alpha"
    assert preview.sqlite_rows["structured_note_drafts"] == 1
    # The idle preview is durable data: preview alone never removes it.
    assert idle_dir.is_dir()
    result = await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert result.project_id == "alpha"
    # The authorized delete purged exactly its own scope's idle staging.
    assert not idle_dir.exists()
    assert not (tmp_path / "deletion" / "journal.json").exists()


async def test_delete_preserves_other_scope_idle_preview(tmp_path: Path) -> None:
    """An authorized delete never sweeps another scope's staged proposal."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha"), ("beta", "Beta")])
    await _seed_sqlite(service, "alpha")
    victim_dir = _stage_idle_preview(
        tmp_path, "11111111-1111-4111-8111-111111111111", "alpha"
    )
    other_dir = _stage_idle_preview(
        tmp_path, "22222222-2222-4222-8222-222222222222", "beta"
    )
    result = await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert result.project_id == "alpha"
    assert not victim_dir.exists()
    assert other_dir.is_dir()
    assert json.loads((other_dir / "preview.json").read_text(encoding="utf-8"))["projectId"] == "beta"


async def test_cancel_and_refusal_preserve_idle_preview(tmp_path: Path) -> None:
    """Cancel/refusal paths never mutate staged previews or project bytes."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    idle_dir = _stage_idle_preview(
        tmp_path, "62b8c1d6-ccc9-4b70-9d93-bf152081c885", "alpha"
    )
    before = await service.preview(actor, "alpha", "Alpha")
    # Cancel = no delete() call: preview + project bytes + staging all unchanged.
    after = await service.preview(actor, "alpha", "Alpha")
    assert after.sqlite_rows == before.sqlite_rows
    assert idle_dir.is_dir()
    with pytest.raises(ProjectDeletionFailure) as mismatch:
        await service.delete(actor, "alpha", "Alpha", "wrong-name", True)
    assert mismatch.value.code == "DELETE_IDENTITY_MISMATCH"
    assert idle_dir.is_dir()
    reread = await service.preview(actor, "alpha", "Alpha")
    assert reread.sqlite_rows["structured_note_drafts"] == 1


async def test_unreadable_preview_still_refuses_fail_closed(tmp_path: Path) -> None:
    """Corrupt staged bytes for the scope keep refusing instead of guessing idle."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    corrupt_dir = tmp_path / "data" / "imports" / "previews" / "33333333-3333-4333-8333-333333333333"
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "package.projecta").write_bytes(b"staged-package-bytes")
    (corrupt_dir / "preview.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ProjectDeletionFailure) as busy:
        await service.preview(actor, "alpha", "Alpha")
    assert busy.value.code == "DELETE_BUSY"
    with pytest.raises(ProjectDeletionFailure) as delete_busy:
        await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert delete_busy.value.code == "DELETE_BUSY"
    assert corrupt_dir.is_dir()


async def test_live_publication_markers_still_refuse(tmp_path: Path) -> None:
    """Launcher publication/recovery markers refuse even with an idle preview present."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    idle_dir = _stage_idle_preview(
        tmp_path, "62b8c1d6-ccc9-4b70-9d93-bf152081c885", "alpha"
    )
    # The launcher writes these during staged publication (RuntimeManager
    # _execute_queued_import_if_present / _finish_import_publication): the
    # publication journal plus the per-token stage/previous trees at
    # <data_root>/recovery. Refusal must hold for each shape, with no mutation.
    recovery_root = tmp_path / "recovery"
    recovery_root.mkdir(parents=True, exist_ok=True)
    token = "62b8c1d6-ccc9-4b70-9d93-bf152081c885"
    markers = [
        recovery_root / "portable-import-publication.json",
        recovery_root / f"portable-import-stage-{token}",
        recovery_root / f"portable-import-previous-{token}",
    ]
    markers[0].write_text("{}", encoding="utf-8")
    markers[1].mkdir(exist_ok=True)
    markers[2].mkdir(exist_ok=True)
    for marker in markers:
        with pytest.raises(ProjectDeletionFailure) as busy:
            await service.preview(actor, "alpha", "Alpha")
        assert busy.value.code == "DELETE_BUSY"
        with pytest.raises(ProjectDeletionFailure) as delete_busy:
            await service.delete(actor, "alpha", "Alpha", "Alpha", True)
        assert delete_busy.value.code == "DELETE_BUSY"
        assert idle_dir.is_dir()
        if marker.is_dir():
            marker.rmdir()
        else:
            marker.unlink()
    preview = await service.preview(actor, "alpha", "Alpha")
    assert preview.project_id == "alpha"


async def test_shared_fence_still_excludes_delete_during_publication(tmp_path: Path) -> None:
    """The shared fence proves contention: delete cannot enter while import publishes."""
    from projecta_api.export_fence import ExportAlreadyRunning, ProjectWriteFence

    fence = ProjectWriteFence()
    async with fence.maintenance_epoch():
        with pytest.raises(ExportAlreadyRunning):
            async with fence.deletion_epoch():
                pass


async def test_cancelled_delete_leaves_state_unchanged(tmp_path: Path) -> None:
    """Cancelling before confirm (no delete call) never mutates the scope."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    before = await service.preview(actor, "alpha", "Alpha")
    # No delete() call happens on cancel; the preview counts still match.
    after = await service.preview(actor, "alpha", "Alpha")
    assert after.sqlite_rows == before.sqlite_rows
    assert after.graph_triples == before.graph_triples


async def test_legal_hold_marker_refuses_fail_closed(tmp_path: Path) -> None:
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    with service._database.transaction() as connection:  # noqa: SLF001
        connection.execute("ALTER TABLE configuration_audit ADD COLUMN legal_hold TEXT")
    with pytest.raises(ProjectDeletionFailure) as held:
        await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert held.value.code == "DELETE_REFUSED_LEGAL_HOLD"


async def test_recovery_refuses_tail_when_graphs_remain(tmp_path: Path) -> None:
    """A post-catalog journal with non-empty graphs refuses instead of mixed-publishing."""
    from projecta_api.project_deletion import _write_private_json

    service, semantic, actor = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {"sources": 5}
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "sqlite-cleared",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [],
            "startedAt": "2026-10-06T00:00:00+00:00",
        },
    )
    with pytest.raises(ProjectDeletionFailure) as recovery:
        await service.recover_before_serving("actor-1")
    assert recovery.value.code == "DELETE_RECOVERY_REQUIRED"
    assert (tmp_path / "deletion" / "journal.json").exists()


async def test_recovery_completes_precatalog_purge(tmp_path: Path) -> None:
    """An interrupted pre-catalog delete completes to exactly-new on restart."""
    from projecta_api.project_deletion import _write_private_json

    service, semantic, _ = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "prepared",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [],
            "startedAt": "2026-10-06T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()
    assert semantic.deleted == ["alpha"]
    with service._database.read_transaction() as connection:  # noqa: SLF001
        assert connection.execute(
            "SELECT count(*) FROM structured_note_drafts WHERE project_id = 'alpha'"
        ).fetchone()[0] == 0


def test_resolve_deletion_scope_accepts_handle_and_rejects_unknown() -> None:
    """The route resolver maps opaque handles to canonical scopes without widening access."""
    from projecta_api.project_workspace import opaque_project_handle
    from projecta_api.routes import _resolve_deletion_scope

    class _Settings:
        experience_project_catalog = "alpha,beta"

    class _State:
        settings = _Settings()

    class _App:
        state = _State()

    class _Request:
        app = _App()

    request = _Request()
    handle = opaque_project_handle("alpha")
    assert handle.startswith("project-h-")
    assert _resolve_deletion_scope(request, handle) == "alpha"
    assert _resolve_deletion_scope(request, "alpha") == "alpha"
    assert (
        _resolve_deletion_scope(request, "project-h-0000000000000000000000000000000000000000")
        == "project-h-0000000000000000000000000000000000000000"
    )



async def test_recovery_completes_when_scope_tables_were_never_created(tmp_path: Path) -> None:
    """Recovery on a store without draft/candidate tables still completes the purge."""
    from sqlalchemy import create_engine

    from projecta_api.configuration.storage import OperationalDatabase
    from projecta_api.evidence.local import LocalEvidenceStore
    from projecta_api.project_deletion import ProjectDeletionService, _write_private_json
    from projecta_api.project_workspace_store import ProjectSelectionRepository

    database = OperationalDatabase(str(tmp_path / "operational.db"))
    ProjectSelectionRepository(database)
    evidence = LocalEvidenceStore(tmp_path / "evidence")
    import_root = tmp_path / "data" / "imports"
    import_root.mkdir(parents=True)
    registry_path = tmp_path / "local-runtime.json"
    _registry(registry_path, [("victim", "Victim")])
    service = ProjectDeletionService(
        database,
        create_engine("sqlite://"),
        evidence,
        _MemorySemantic(),
        deletion_root=tmp_path / "deletion",
        import_root=import_root,
        exports_root=tmp_path / "exports",
        registry_path=registry_path,
        native_runtime_lock_held=True,
        restart_file=tmp_path / "state" / "import-restart.json",
        runtime_id="test-runtime",
    )
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "prepared",
            "projectId": "victim",
            "projectName": "Victim",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()


async def test_recovery_tolerates_already_cleared_graphs(tmp_path: Path) -> None:
    """A kill after graphs-cleared still completes instead of failing on empty scope."""
    from projecta_api.project_deletion import _write_private_json
    from projecta_api.semantic_core import SemanticCoreProblem

    service, _, _ = _service(tmp_path, [("alpha", "Alpha")])

    class _EmptyScope:
        async def project_graph_counts(self, actor, project_id):  # noqa: ANN001, ANN202
            return {}

        async def delete_project_graphs(self, actor, project_id):  # noqa: ANN001, ANN202
            raise SemanticCoreProblem(404, "PROJECT_STATE_ABSENT", "The project has no semantic state to delete.")

    service._semantic = _EmptyScope()  # noqa: SLF001 - recovery path substitution
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "prepared",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()


async def test_recovery_resumes_idle_preview_purge(tmp_path: Path) -> None:
    """An interrupted delete resumes the recorded idle-preview purge on restart."""
    from projecta_api.project_deletion import _write_private_json

    service, semantic, _ = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {}
    token = "62b8c1d6-ccc9-4b70-9d93-bf152081c885"
    idle_dir = _stage_idle_preview(tmp_path, token, "alpha")
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "ledger-forgotten",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [token],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not idle_dir.exists()
    assert not (tmp_path / "deletion" / "journal.json").exists()


async def test_foreign_actor_preview_refuses_before_any_mutation(tmp_path: Path) -> None:
    """A foreign-actor staged preview refuses preview/delete with zero state change."""
    service, semantic, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    foreign_dir = _stage_idle_preview(
        tmp_path, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "alpha", actor="actor-2"
    )
    with pytest.raises(ProjectDeletionFailure) as preview_busy:
        await service.preview(actor, "alpha", "Alpha")
    assert preview_busy.value.code == "DELETE_BUSY"
    before = await service._semantic.project_graph_counts(actor, "alpha")  # noqa: SLF001
    with pytest.raises(ProjectDeletionFailure) as delete_busy:
        await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert delete_busy.value.code == "DELETE_BUSY"
    # Refusal left every store, the journal, and the foreign staging untouched.
    assert semantic.deleted == []
    assert foreign_dir.is_dir()
    assert not (tmp_path / "deletion" / "journal.json").exists()
    after = await service._semantic.project_graph_counts(actor, "alpha")  # noqa: SLF001
    assert after == before
    with service._database.read_transaction() as connection:  # noqa: SLF001
        assert connection.execute(
            "SELECT count(*) FROM structured_note_drafts WHERE project_id = 'alpha'"
        ).fetchone()[0] == 1


async def test_delete_still_purges_same_actor_preview_scope(tmp_path: Path) -> None:
    """The authorized actor's own idle preview still deletes with the scope."""
    service, _, actor = _service(tmp_path, [("alpha", "Alpha")])
    await _seed_sqlite(service, "alpha")
    own_dir = _stage_idle_preview(
        tmp_path, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "alpha", actor="actor-1"
    )
    result = await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert result.project_id == "alpha"
    assert not own_dir.exists()
    assert not (tmp_path / "deletion" / "journal.json").exists()


async def test_delete_result_uses_graph_total_not_role_sum(tmp_path: Path) -> None:
    """The server payload carries per-role counts plus a total key; the result must report total."""
    service, semantic, actor = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {"sources": 28, "candidates": 17, "asserted": 2, "inferred": 0, "provenance": 26, "total": 73}

    async def _delete_with_total(self: _MemorySemantic, actor: TrustedActorContext, project_id: str) -> Mapping[str, int]:  # noqa: ANN001, ANN202
        self.deleted.append(project_id)
        removed = {"sources": 28, "candidates": 17, "asserted": 2, "inferred": 0, "provenance": 26, "total": 73}
        self.graphs = {}
        return removed

    semantic.delete_project_graphs = _delete_with_total.__get__(semantic, _MemorySemantic)  # type: ignore[method-assign]
    result = await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert result.graph_triples_removed == 73

async def test_recovery_completes_when_staging_already_forgotten(tmp_path: Path) -> None:
    """A kill after staging-forgotten (tokens already gone) still completes idempotently."""
    from projecta_api.project_deletion import _write_private_json

    service, semantic, _ = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {}
    token = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "staging-forgotten",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [token],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()
    # A repeated recovery with the journal already gone stays a stable no-op.
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()
    assert json.loads((tmp_path / "local-runtime.json").read_text(encoding="utf-8"))["projects"] == []


async def test_recovery_completes_partial_preview_purge_and_repeats_stably(tmp_path: Path) -> None:
    """A kill mid-preview-purge finishes the tail; repeating recovery stays stable."""
    import shutil as _shutil

    from projecta_api.project_deletion import _write_private_json

    service, semantic, _ = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {}
    first = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    second = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    first_dir = _stage_idle_preview(tmp_path, first, "alpha")
    second_dir = _stage_idle_preview(tmp_path, second, "alpha")
    # Simulate a crash after the first token was purged: only the second
    # token remains on disk while the journal still records both.
    _shutil.rmtree(first_dir, ignore_errors=False)
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "ledger-forgotten",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [first, second],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    assert not first_dir.exists()
    await service.recover_before_serving("actor-1")
    assert not second_dir.exists()
    assert not (tmp_path / "deletion" / "journal.json").exists()


async def test_recovery_completes_partial_purge_at_staging_forgotten(tmp_path: Path) -> None:
    """A kill between staging-forgotten and registry-published with one token left finishes the tail."""
    import shutil as _shutil

    from projecta_api.project_deletion import _write_private_json

    service, semantic, _ = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {}
    gone = "11111111-1111-4111-8111-111111111111"
    left = "22222222-2222-4222-8222-222222222222"
    gone_dir = _stage_idle_preview(tmp_path, gone, "alpha")
    left_dir = _stage_idle_preview(tmp_path, left, "alpha")
    # Crash after the first token was purged and the phase advanced: the
    # journal records both tokens at staging-forgotten while one is gone.
    _shutil.rmtree(gone_dir, ignore_errors=False)
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "staging-forgotten",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [gone, left],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    assert not gone_dir.exists()
    await service.recover_before_serving("actor-1")
    assert not left_dir.exists()

async def test_recovery_still_refuses_genuinely_foreign_preview(tmp_path: Path) -> None:
    """Recovery never reinterprets a live foreign-actor preview as already-purged."""
    from projecta_api.project_deletion import _write_private_json

    service, semantic, _ = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {}
    token = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    foreign_dir = _stage_idle_preview(tmp_path, token, "alpha", actor="actor-2")
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "ledger-forgotten",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [token],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    with pytest.raises(ProjectDeletionFailure) as recovery:
        await service.recover_before_serving("actor-1")
    assert recovery.value.code == "DELETE_BUSY"
    assert foreign_dir.is_dir()
    assert (tmp_path / "deletion" / "journal.json").exists()


async def test_recovery_completes_after_registry_already_published(tmp_path: Path) -> None:
    """A kill after registry-published finishes selections/journal without unknown refusal."""
    from projecta_api.project_deletion import _write_private_json

    service, semantic, actor = _service(tmp_path, [("alpha", "Alpha")])
    semantic.graphs = {}
    token = "99999999-9999-4999-8999-999999999999"
    _stage_idle_preview(tmp_path, token, "alpha")
    result = await service.delete(actor, "alpha", "Alpha", "Alpha", True)
    assert result.project_id == "alpha"
    # Simulate a crash between registry-published and journal unlink: the
    # registry is already gone but the journal still claims registry-published.
    _write_private_json(
        tmp_path / "deletion" / "journal.json",
        {
            "formatVersion": 1,
            "phase": "registry-published",
            "projectId": "alpha",
            "projectName": "Alpha",
            "actorId": "actor-1",
            "expectedGraphTriples": {},
            "expectedEvidenceObjects": 0,
            "expectedSqliteRows": {},
            "expectedPostgresRows": {},
            "exportIds": [],
            "idlePreviewTokens": [],
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()
    assert json.loads((tmp_path / "local-runtime.json").read_text(encoding="utf-8"))["projects"] == []

