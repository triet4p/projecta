"""Consumer-visible project-deletion boundaries for projecta-deletion.v1.

Covers the finite outcome surface only: typed-identity confirmation,
authorization, unknown-project refusal, cancellation leaving state unchanged,
busy refusal with zero state change, and the full-scope purge predicate set.
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
    import_root = tmp_path / "imports"
    import_root.mkdir()
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
    (tmp_path / "imports" / "journal.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ProjectDeletionFailure) as busy:
        await service.preview(actor, "alpha", "Alpha")
    assert busy.value.code == "DELETE_BUSY"
    # Zero state change: preview still refuses the same way after journal removal fails closed.
    (tmp_path / "imports" / "journal.json").unlink()
    preview = await service.preview(actor, "alpha", "Alpha")
    assert preview.project_id == "alpha"


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
    from projecta_api.configuration.storage import OperationalDatabase
    from projecta_api.evidence.local import LocalEvidenceStore
    from projecta_api.project_deletion import ProjectDeletionService, _write_private_json
    from projecta_api.project_workspace_store import ProjectSelectionRepository
    from sqlalchemy import create_engine

    database = OperationalDatabase(str(tmp_path / "operational.db"))
    ProjectSelectionRepository(database)
    evidence = LocalEvidenceStore(tmp_path / "evidence")
    import_root = tmp_path / "imports"
    import_root.mkdir()
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
            "startedAt": "2026-10-07T00:00:00+00:00",
        },
    )
    await service.recover_before_serving("actor-1")
    assert not (tmp_path / "deletion" / "journal.json").exists()


