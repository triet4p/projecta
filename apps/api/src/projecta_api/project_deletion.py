"""Native-only single-project purge for the approved projecta-deletion.v1 contract.

Deletes exactly one explicitly confirmed project scope across every
project-owned store (contract §§3-4): five semantic graphs, evidence trees,
SQLite workflow/cost/config-audit/LLM state, PostgreSQL connector/review
history via migration ``0012``, import-ledger scope keys, registry entry and
actor selections. Anything outside the scope (other projects, shared config,
global audit/sessions, exports, backups) is never touched.

Safety shape (contract §5):

- native-only: the service runs only when the native lock + roots + engines
  are present (same ``enabled()`` shape as the portable import service). There
  is no browser-supplied SQL anywhere on this path; every store call carries
  an exact ``project_id``/``project_digest`` predicate.
- quiescence: ``delete()`` must run inside the API ``maintenance_epoch`` (the
  route owns the fence). The service additionally refuses when an import
  journal/restart marker exists, when any import preview/result entry targets
  the scope, or when active connector runs or pending suggestion workflows
  exist for the scope.
- journal: ``data/deletion/journal.json`` records the finite phase before each
  store mutation; ``recover_before_serving()`` resolves an interrupted delete
  to exactly-old or exactly-new state before the API serves traffic.
- ordinary append-only guards stay enforcing: guarded history rows are removed
  only through the reviewed ``0012`` helper (transaction-local named-trigger
  window, verified re-enabled pre-commit) and the serialized SQLite purge
  transaction (drop/recreate inside the transaction, verified after).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

from sqlalchemy import Engine, text

from projecta_api.configuration.storage import OperationalDatabase
from projecta_api.context import TrustedActorContext
from projecta_api.evidence.local import LocalEvidenceStore

_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SQLITE_SCOPE_TABLES = (
    "structured_note_drafts",
    "structured_candidate_edits",
    "local_suggestion_workflows",
    "local_suggestion_attempts",
    "local_suggestion_budget_counters",
)
_PG_SCOPE_TABLES = (
    "connector_installations",
    "teams_setup_handles",
    "github_public_issues_setup_handles",
    "connector_event_inbox",
    "connector_sync_runs",
    "connector_cursors",
    "connector_dead_letters",
    "connector_audit_records",
    "review_decision_receipts",
    "correction_burden_events",
)
_JOURNAL_PHASES = (
    "prepared",
    "graphs-cleared",
    "evidence-cleared",
    "sqlite-cleared",
    "postgres-cleared",
    "ledger-forgotten",
    "registry-published",
)
_AUTHORING_COST_TRIGGERS_SQL = (
    "CREATE TRIGGER authoring_cost_events_append_only_update\n"
    "    BEFORE UPDATE ON authoring_cost_events\n"
    "    BEGIN SELECT RAISE(ABORT, 'authoring_cost_events is append-only'); END;",
    "CREATE TRIGGER authoring_cost_events_append_only_delete\n"
    "    BEFORE DELETE ON authoring_cost_events\n"
    "    BEGIN SELECT RAISE(ABORT, 'authoring_cost_events is append-only'); END;",
)


class ProjectDeletionFailure(RuntimeError):
    """Finite deletion failure with a truthful outcome code and HTTP status."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class SemanticDeletionClient(Protocol):
    async def project_graph_counts(
        self, actor: TrustedActorContext, project_id: str
    ) -> Mapping[str, int]: ...

    async def delete_project_graphs(
        self, actor: TrustedActorContext, project_id: str
    ) -> Mapping[str, int]: ...


@dataclass(frozen=True, slots=True)
class ProjectDeletionPreview:
    project_id: str
    project_name: str
    graph_triples: Mapping[str, int]
    evidence_objects: int
    sqlite_rows: Mapping[str, int]
    postgres_rows: Mapping[str, int]
    ledger_entries: int
    warnings: tuple[str, ...]

    def response(self) -> dict[str, object]:
        return {
            "projectId": self.project_id,
            "projectName": self.project_name,
            "graphTriples": dict(self.graph_triples),
            "evidenceObjects": self.evidence_objects,
            "sqliteRows": dict(self.sqlite_rows),
            "postgresRows": dict(self.postgres_rows),
            "ledgerEntries": self.ledger_entries,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ProjectDeletionResult:
    project_id: str
    project_name: str
    graph_triples_removed: int
    evidence_objects_removed: int
    sqlite_rows_removed: int
    postgres_rows_removed: int
    ledger_entries_forgotten: int
    memberships_removed: int

    def response(self) -> dict[str, object]:
        return {
            "projectId": self.project_id,
            "projectName": self.project_name,
            "outcome": "deleted",
            "restartRequired": True,
            "nextAction": (
                "Projecta Local is restarting to serve the new project catalog. "
                "The deleted project is gone; select a remaining project from Projects when ready."
            ),
            "graphTriplesRemoved": self.graph_triples_removed,
            "evidenceObjectsRemoved": self.evidence_objects_removed,
            "sqliteRowsRemoved": self.sqlite_rows_removed,
            "postgresRowsRemoved": self.postgres_rows_removed,
            "ledgerEntriesForgotten": self.ledger_entries_forgotten,
            "membershipsRemoved": self.memberships_removed,
            "retained": [
                "other projects unchanged",
                "installation secrets and configuration unchanged",
                "exported .projecta files unchanged",
                "whole-installation backups unchanged",
            ],
        }


class ProjectDeletionService:
    """Preview and purge exactly one confirmed native project scope."""

    def __init__(
        self,
        database: OperationalDatabase,
        postgres_engine: Engine | None,
        evidence_store: LocalEvidenceStore,
        semantic: SemanticDeletionClient,
        deletion_root: Path | None,
        import_root: Path | None,
        exports_root: Path | None,
        registry_path: Path | None,
        native_runtime_lock_held: bool,
        identity_repository: object | None = None,
        restart_file: Path | None = None,
        runtime_id: str = "",
    ) -> None:
        self._database = database
        self._postgres_engine = postgres_engine
        self._evidence = evidence_store
        self._semantic = semantic
        self._root = deletion_root
        self._import_root = import_root
        self._exports_root = exports_root
        self._registry_path = registry_path
        self._native_runtime_lock_held = native_runtime_lock_held
        self._identity_repository = identity_repository
        self._restart_file = restart_file
        self._runtime_id = runtime_id

    def enabled(self) -> bool:
        return bool(
            self._native_runtime_lock_held
            and self._postgres_engine is not None
            and self._root is not None
            and self._import_root is not None
            and self._registry_path is not None
        )

    def _require_enabled(self) -> None:
        if not self.enabled():
            raise ProjectDeletionFailure("DELETE_UNSUPPORTED_RUNTIME", status_code=503)

    async def preview(
        self, actor: TrustedActorContext, project_id: str, project_name: str
    ) -> ProjectDeletionPreview:
        """Count every owned row/object for the scope without mutating anything."""
        self._require_enabled()
        resolved_id, resolved_name = self._resolve_scope(actor, project_id, project_name)
        self._refuse_active_operation(resolved_id)
        graph_triples = await self._semantic.project_graph_counts(actor, resolved_id)
        evidence_objects = len(await self._evidence.list_project(resolved_id))
        sqlite_rows = self._sqlite_scope_counts(resolved_id)
        postgres_rows = self._postgres_scope_counts(resolved_id)
        ledger_entries = len(self._scope_export_ids(resolved_id))
        return ProjectDeletionPreview(
            project_id=resolved_id,
            project_name=resolved_name,
            graph_triples=dict(graph_triples),
            evidence_objects=evidence_objects,
            sqlite_rows=sqlite_rows,
            postgres_rows=postgres_rows,
            ledger_entries=ledger_entries,
            warnings=(
                "Deleting this project permanently removes ALL of its data and history, "
                "including review receipts, correction history, cost history and configuration "
                "audit rows. There is no undo.",
                "Previously exported .projecta files and whole-installation backups are NOT deleted.",
                "The same project ID can be freshly imported afterwards.",
            ),
        )

    async def delete(
        self,
        actor: TrustedActorContext,
        project_id: str,
        project_name: str,
        typed_identity: str,
        confirmed: bool,
    ) -> ProjectDeletionResult:
        """Purge the confirmed scope through the journal-driven phase order."""
        self._require_enabled()
        if confirmed is not True:
            raise ProjectDeletionFailure("DELETE_CONFIRMATION_REQUIRED", status_code=400)
        resolved_id, resolved_name = self._resolve_scope(actor, project_id, project_name)
        if typed_identity.strip() not in (resolved_id, resolved_name):
            raise ProjectDeletionFailure("DELETE_IDENTITY_MISMATCH", status_code=400)
        self._refuse_active_operation(resolved_id)
        self._scan_unknown_hold_markers(resolved_id)
        assert self._root is not None
        journal_path = self._root / "journal.json"
        if journal_path.exists():
            raise ProjectDeletionFailure("DELETE_BUSY", status_code=409)
        graph_triples = await self._semantic.project_graph_counts(actor, resolved_id)
        evidence_objects = len(await self._evidence.list_project(resolved_id))
        sqlite_rows = self._sqlite_scope_counts(resolved_id)
        postgres_rows = self._postgres_scope_counts(resolved_id)
        export_ids = self._scope_export_ids(resolved_id)
        journal: dict[str, object] = {
            "formatVersion": 1,
            "phase": "prepared",
            "projectId": resolved_id,
            "projectName": resolved_name,
            "actorId": actor.actor_id,
            "expectedGraphTriples": dict(graph_triples),
            "expectedEvidenceObjects": evidence_objects,
            "expectedSqliteRows": dict(sqlite_rows),
            "expectedPostgresRows": dict(postgres_rows),
            "exportIds": sorted(export_ids),
            "startedAt": datetime.now(UTC).isoformat(),
        }
        _write_private_json(journal_path, journal)
        try:
            cleared_graphs = await self._semantic.delete_project_graphs(actor, resolved_id)
            journal["phase"] = "graphs-cleared"
            _write_private_json(journal_path, journal)
            await self._evidence.remove_project_for_import(resolved_id)
            journal["phase"] = "evidence-cleared"
            _write_private_json(journal_path, journal)
            sqlite_removed = self._purge_sqlite_scope(resolved_id)
            journal["phase"] = "sqlite-cleared"
            _write_private_json(journal_path, journal)
            postgres_removed = self._purge_postgres_scope(resolved_id)
            journal["phase"] = "postgres-cleared"
            _write_private_json(journal_path, journal)
            ledger_forgotten = self._forget_ledger_scope(export_ids)
            journal["phase"] = "ledger-forgotten"
            _write_private_json(journal_path, journal)
            memberships_removed = self._remove_memberships(resolved_id)
            self._publish_registry_removal(resolved_id)
            journal["phase"] = "registry-published"
            _write_private_json(journal_path, journal)
            self._clear_selections(resolved_id)
            journal_path.unlink(missing_ok=True)
            # The running API still carries the pre-delete allowlist; ask the
            # launcher to restart services so the catalog serves the new set.
            self._request_runtime_restart()
            return ProjectDeletionResult(
                project_id=resolved_id,
                project_name=resolved_name,
                graph_triples_removed=sum(int(value) for value in cleared_graphs.values()),
                evidence_objects_removed=evidence_objects,
                sqlite_rows_removed=sqlite_removed,
                postgres_rows_removed=postgres_removed,
                ledger_entries_forgotten=ledger_forgotten,
                memberships_removed=memberships_removed,
            )
        except ProjectDeletionFailure:
            raise
        except Exception as error:
            phase = str(journal.get("phase", "prepared"))
            if phase in {"prepared", "graphs-cleared", "evidence-cleared"}:
                raise ProjectDeletionFailure("DELETE_FAILED", status_code=503) from error
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503) from error

    async def recover_before_serving(self, actor_id: str) -> None:
        """Resolve an interrupted delete to exactly-old or exactly-new state."""
        if not self.enabled():
            return
        assert self._root is not None and self._registry_path is not None
        journal_path = self._root / "journal.json"
        if not journal_path.exists():
            return
        journal = _read_private_json(journal_path)
        phase = journal.get("phase")
        if (
            set(journal)
            != {
                "formatVersion", "phase", "projectId", "projectName", "actorId",
                "expectedGraphTriples", "expectedEvidenceObjects", "expectedSqliteRows",
                "expectedPostgresRows", "exportIds", "startedAt",
            }
            or journal.get("formatVersion") != 1
            or journal.get("actorId") != actor_id
            or phase not in _JOURNAL_PHASES
        ):
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        project_id = str(journal["projectId"])
        recovery_actor = TrustedActorContext(actor_id=actor_id, request_id="delete-recovery", operation_id="delete-recovery")
        if phase in {"prepared", "graphs-cleared", "evidence-cleared"}:
            # Catalog was never published and graphs may be partially cleared
            # with no snapshot to roll back to, so the only safe resolution is
            # to COMPLETE the purge (never a rollback to a half-cleared past).
            # A journal that claims a later phase while graphs/evidence remain
            # is inconsistent and refuses instead of mixed-publishing.
            await self._clear_graphs_idempotent(recovery_actor, project_id)
            self._purge_sqlite_scope(project_id)
            self._purge_postgres_scope(project_id)
            self._forget_ledger_scope({str(value) for value in cast(Sequence[object], journal["exportIds"])})
            self._remove_memberships(project_id)
            self._publish_registry_removal(project_id)
            self._clear_selections(project_id)
            journal_path.unlink(missing_ok=True)
            self._request_runtime_restart()
            return
        # Catalog publication is the commit boundary; finish the tail so the
        # scope is exactly gone instead of half-published. A journal at or past
        # sqlite-cleared is only reachable after graphs-cleared, so the scope
        # graphs must already be empty; otherwise the journal is inconsistent
        # (or synthetic) and recovery refuses instead of publishing a mixed state.
        remaining_graphs = await self._semantic.project_graph_counts(recovery_actor, project_id)
        if sum(int(value) for value in remaining_graphs.values()) != 0:
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        if await self._evidence.list_project(project_id):
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        export_ids = {str(value) for value in cast(Sequence[object], journal["exportIds"])}
        if phase in {"sqlite-cleared", "postgres-cleared", "ledger-forgotten"}:
            self._purge_postgres_scope(project_id)
            self._forget_ledger_scope(export_ids)
            self._remove_memberships(project_id)
        self._publish_registry_removal(project_id)
        self._clear_selections(project_id)
        journal_path.unlink(missing_ok=True)
        self._request_runtime_restart()

    def _request_runtime_restart(self) -> None:
        if self._restart_file is None or not self._runtime_id:
            return
        _write_private_json(
            self._restart_file,
            {"runtimeId": self._runtime_id, "requestedAt": datetime.now(UTC).isoformat(), "restart": True},
        )

    def _resolve_scope(
        self, actor: TrustedActorContext, project_id: str, project_name: str
    ) -> tuple[str, str]:
        assert self._registry_path is not None
        if not _PROJECT_ID.fullmatch(project_id):
            raise ProjectDeletionFailure("DELETE_UNKNOWN_PROJECT", status_code=404)
        registry = _read_registry(self._registry_path)
        if actor.actor_id != registry.get("actorId"):
            raise ProjectDeletionFailure("DELETE_UNAUTHORIZED", status_code=403)
        entries = _registry_entries(registry)
        match = next((item for item in entries if item["projectId"] == project_id), None)
        if match is None:
            raise ProjectDeletionFailure("DELETE_UNKNOWN_PROJECT", status_code=404)
        if not project_name or project_name.strip() != match["projectName"]:
            raise ProjectDeletionFailure("DELETE_IDENTITY_MISMATCH", status_code=400)
        return project_id, match["projectName"]

    def _refuse_active_operation(self, project_id: str) -> None:
        assert self._import_root is not None
        journal_path = self._import_root / "journal.json"
        # Any live import journal blocks deletion: staged state belongs to the
        # import operation and must never be swept by a project delete.
        if journal_path.exists() or (self._import_root / "import-restart.json").exists():
            raise ProjectDeletionFailure("DELETE_BUSY", status_code=409)
        previews_root = self._import_root / "previews"
        if previews_root.is_dir() and not previews_root.is_symlink():
            for preview_file in sorted(previews_root.glob("*/preview.json")):
                try:
                    preview = json.loads(preview_file.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, ValueError):
                    raise ProjectDeletionFailure("DELETE_BUSY", status_code=409)
                if isinstance(preview, dict) and preview.get("projectId") == project_id:
                    # A staged preview targets this scope: cancel it first, then
                    # delete. Retained previews are never swept by deletion.
                    raise ProjectDeletionFailure("DELETE_BUSY", status_code=409)
        if self._has_active_connector_runs(project_id):
            raise ProjectDeletionFailure("DELETE_BUSY", status_code=409)
        if self._has_pending_suggestion_workflows(project_id):
            raise ProjectDeletionFailure("DELETE_BUSY", status_code=409)

    def _has_active_connector_runs(self, project_id: str) -> bool:
        assert self._postgres_engine is not None
        try:
            with self._postgres_engine.connect() as connection:
                active = connection.execute(
                    text(
                        "SELECT 1 FROM connector_sync_runs "
                        "WHERE project_id = :project_id AND terminal_at IS NULL LIMIT 1"
                    ),
                    {"project_id": project_id},
                ).first()
                return active is not None
        except Exception as error:
            if "no such table" not in str(error).lower():
                raise
            return False

    def _has_pending_suggestion_workflows(self, project_id: str) -> bool:
        with self._database.read_transaction() as connection:
            row = connection.execute(
                "SELECT 1 FROM local_suggestion_workflows "
                "WHERE project_id = ? AND state IN ('new', 'pending') LIMIT 1",
                (project_id,),
            ).fetchone()
            return row is not None

    async def _clear_graphs_idempotent(self, actor: TrustedActorContext, project_id: str) -> None:
        """Clear the scope graphs, tolerating an already-empty scope.

        Recovery re-runs the purge after a mid-purge kill: the first attempt
        may already have cleared the graphs, so Core's empty-scope refusal
        (`PROJECT_STATE_ABSENT`) means done, not failed. Any other Core
        failure still raises.
        """
        from projecta_api.semantic_core import SemanticCoreProblem

        try:
            await self._semantic.delete_project_graphs(actor, project_id)
        except SemanticCoreProblem as error:
            if error.code != "PROJECT_STATE_ABSENT":
                raise

    def _scan_unknown_hold_markers(self, project_id: str) -> None:
        """Fail closed on any unrecognized legal-hold marker for the scope.

        No ``legal_hold`` concept exists in v1 source, so this scan passes on
        current stores. It exists so a future hold marker can never be silently
        purged: any key/column whose name suggests a hold refuses the delete.
        """
        markers = ("legal_hold", "legalhold", "legal-hold")
        with self._database.read_transaction() as connection:
            columns = {
                str(row["name"])
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            for table in sorted(columns):
                if not table.startswith(("structured_", "local_suggestion_", "authoring_", "configuration_", "llm_")):
                    continue
                try:
                    table_columns = {
                        str(row[1]).lower()
                        for row in connection.execute(f'PRAGMA table_info("{table}")')
                    }
                except Exception as error:
                    raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503) from error
                if any(any(marker in column for marker in markers) for column in table_columns):
                    raise ProjectDeletionFailure("DELETE_REFUSED_LEGAL_HOLD", status_code=409)
        assert self._postgres_engine is not None
        try:
            with self._postgres_engine.connect() as connection:
                for table in _PG_SCOPE_TABLES:
                    columns = connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = :table"
                        ),
                        {"table": table},
                    ).all()
                    if any(
                        any(marker in str(row[0]).lower() for marker in markers) for row in columns
                    ):
                        raise ProjectDeletionFailure("DELETE_REFUSED_LEGAL_HOLD", status_code=409)
        except ProjectDeletionFailure:
            raise
        except Exception as error:
            if "no such table" not in str(error).lower() and "undefined_table" not in str(error).lower():
                raise

    def _sqlite_scope_counts(self, project_id: str) -> dict[str, int]:
        digest = _digest_text(project_id)
        counts: dict[str, int] = {}
        with self._database.read_transaction() as connection:
            for table in _SQLITE_SCOPE_TABLES:
                counts[table] = int(
                    connection.execute(
                        f"SELECT count(*) FROM {table} WHERE project_id = ?", (project_id,)
                    ).fetchone()[0]
                )
            counts["authoring_cost_events"] = int(
                connection.execute(
                    "SELECT count(*) FROM authoring_cost_events WHERE project_digest = ?",
                    (digest,),
                ).fetchone()[0]
            )
            counts["configuration_audit"] = int(
                connection.execute(
                    "SELECT count(*) FROM configuration_audit WHERE scope = ?", (project_id,)
                ).fetchone()[0]
            )
            counts["llm_profiles"] = int(
                connection.execute(
                    "SELECT count(*) FROM llm_profiles WHERE scope = ? AND active = 1",
                    (project_id,),
                ).fetchone()[0]
            )
        return counts

    def _postgres_scope_counts(self, project_id: str) -> dict[str, int]:
        assert self._postgres_engine is not None
        counts: dict[str, int] = {}
        with self._postgres_engine.connect() as connection:
            for table in _PG_SCOPE_TABLES:
                try:
                    counts[table] = int(
                        connection.execute(
                            text(f"SELECT count(*) FROM {table} WHERE project_id = :project_id"),
                            {"project_id": project_id},
                        ).scalar_one()
                    )
                except Exception as error:
                    # A store without the full connector schema (unit doubles)
                    # reports zero; the real schema is proved on disposable PG.
                    if "no such table" not in str(error).lower():
                        raise
                    counts[table] = 0
            try:
                counts["connector_sync_attempts"] = int(
                    connection.execute(
                        text(
                            "SELECT count(*) FROM connector_sync_attempts a "
                            "JOIN connector_sync_runs r ON r.run_id = a.run_id "
                            "WHERE r.project_id = :project_id"
                        ),
                        {"project_id": project_id},
                    ).scalar_one()
                )
            except Exception as error:
                if "no such table" not in str(error).lower():
                    raise
                counts["connector_sync_attempts"] = 0
        return counts

    def _scope_export_ids(self, project_id: str) -> set[str]:
        """Resolve this scope's ledger keys from archived package manifests.

        The ledger is keyed by ``exportId`` with no ``projectId`` column, so the
        delete resolves exactly this scope's keys from three durable sources:
        retained ``data/exports/*.projecta`` manifests, staged import previews
        for the scope, and completed import result records (the launcher writes
        ``projectId`` + ``exportId`` per completed import). Keys for other
        scopes are never returned.
        """
        export_ids: set[str] = set()
        if self._exports_root is not None and self._exports_root.is_dir():
            for archive in sorted(self._exports_root.glob("*.projecta")):
                manifest_project, export_id = _read_archive_identity(archive)
                if manifest_project == project_id and export_id is not None:
                    export_ids.add(export_id)
        assert self._import_root is not None
        previews_root = self._import_root / "previews"
        if previews_root.is_dir() and not previews_root.is_symlink():
            for preview_file in sorted(previews_root.glob("*/preview.json")):
                try:
                    preview = json.loads(preview_file.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, ValueError):
                    continue
                if (
                    isinstance(preview, dict)
                    and preview.get("projectId") == project_id
                    and isinstance(preview.get("exportId"), str)
                ):
                    export_ids.add(str(preview["exportId"]))
        results_root = self._import_root / "results"
        if results_root.is_dir() and not results_root.is_symlink():
            for result_file in sorted(results_root.glob("*.json")):
                try:
                    record = json.loads(result_file.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, ValueError):
                    continue
                if (
                    isinstance(record, dict)
                    and record.get("projectId") == project_id
                    and isinstance(record.get("exportId"), str)
                ):
                    export_ids.add(str(record["exportId"]))
        ledger = self._read_ledger()
        return {key for key in export_ids if key in ledger}

    def _purge_sqlite_scope(self, project_id: str) -> int:
        """Delete the scope inside ONE serialized transaction.

        The append-only ``authoring_cost_events`` triggers are dropped and
        recreated inside this same transaction from the canonical SQL, then
        verified present and enforcing before commit. Any failure rolls rows
        and triggers back together; concurrent writers serialize on the
        database lock plus the API fence, so they observe old-or-complete-new
        state, never a half-purged scope.
        """
        # NOTE: the scope LLM secret is deleted by locator below through the
        # reviewed per-scope lifecycle (deactivate profile + delete that scope's
        # secret_reference only when unreferenced); shared scopes are untouched.

        digest = _digest_text(project_id)
        removed = 0
        with self._database.transaction() as connection:
            connection.execute("DROP TRIGGER IF EXISTS authoring_cost_events_append_only_update")
            connection.execute("DROP TRIGGER IF EXISTS authoring_cost_events_append_only_delete")
            for table in (
                "structured_candidate_edits",
                "structured_note_drafts",
                "local_suggestion_attempts",
                "local_suggestion_workflows",
                "local_suggestion_budget_counters",
            ):
                try:
                    cursor = connection.execute(
                        f"DELETE FROM {table} WHERE project_id = ?", (project_id,)
                    )
                except Exception as error:
                    if "no such table" not in str(error).lower():
                        raise
                    continue
                removed += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            cursor = connection.execute(
                "DELETE FROM authoring_cost_events WHERE project_digest = ?", (digest,)
            )
            removed += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            cursor = connection.execute(
                "DELETE FROM configuration_audit WHERE scope = ?", (project_id,)
            )
            removed += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            profile = connection.execute(
                "SELECT secret_reference, revision FROM llm_profiles WHERE scope = ? AND active = 1",
                (project_id,),
            ).fetchone()
            secret_reference = str(profile["secret_reference"]) if profile and profile["secret_reference"] else None
            if profile is not None:
                connection.execute(
                    "UPDATE llm_profiles SET active = 0, credential_configured = 0, "
                    "secret_reference = NULL, revision = revision + 1 WHERE scope = ?",
                    (project_id,),
                )
                removed += 1
            if secret_reference:
                holders = connection.execute(
                    "SELECT count(*) FROM llm_profiles WHERE secret_reference = ?",
                    (secret_reference,),
                ).fetchone()[0]
                if int(holders) == 0:
                    connection.execute(
                        "DELETE FROM secret_records WHERE secret_reference = ?",
                        (secret_reference,),
                    )
                    removed += 1
            for trigger_sql in _AUTHORING_COST_TRIGGERS_SQL:
                connection.execute(trigger_sql)
            guards = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name IN "
                "('authoring_cost_events_append_only_update', "
                "'authoring_cost_events_append_only_delete')"
            ).fetchall()
            if len(guards) != 2:
                raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        # Post-commit: the triggers must reject an ordinary guarded write.
        # Insert a sacrificial probe row, verify an ordinary DELETE aborts
        # (guard enforcing), then remove the probe through the same verified
        # trigger lifecycle used for the scope (drop/delete/recreate inside
        # one serialized transaction) so the probe never lingers.
        with self._database.transaction() as probe:
            probe.execute(
                "INSERT INTO authoring_cost_events(event_id, project_digest, actor_digest, "
                "workflow_kind, event_type, occurred_at) VALUES (?, ?, ?, 'entity', "
                "'manual_workflow', ?)",
                ("purge-guard-probe", _digest_text("__purge_guard_probe__"), "sha256:" + "0" * 64, "2026-01-01T00:00:00+00:00"),
            )
        with self._database.transaction() as probe:
            try:
                probe.execute(
                    "DELETE FROM authoring_cost_events WHERE event_id = 'purge-guard-probe'"
                )
            except Exception:
                pass
            else:
                raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        with self._database.transaction() as probe:
            probe.execute("DROP TRIGGER IF EXISTS authoring_cost_events_append_only_delete")
            probe.execute("DELETE FROM authoring_cost_events WHERE event_id = 'purge-guard-probe'")
            probe.execute(_AUTHORING_COST_TRIGGERS_SQL[1])
            guards = probe.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name = "
                "'authoring_cost_events_append_only_delete'"
            ).fetchall()
            if len(guards) != 1:
                raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        return removed

    def _purge_postgres_scope(self, project_id: str) -> int:
        """Delete the scope parent-before-child inside one PG transaction.

        Guarded receipt/correction rows go only through the reviewed ``0012``
        helper (transaction-local named-trigger window, verified re-enabled).
        Every other table uses an exact ``project_id = ?`` predicate; attempts
        resolve through their parent runs. Any failure rolls everything back.
        """
        assert self._postgres_engine is not None
        removed = 0
        try:
            is_postgresql = self._postgres_engine.dialect.name == "postgresql"
        except Exception:
            is_postgresql = True
        with self._postgres_engine.begin() as connection:
            if is_postgresql:
                attempts = connection.execute(
                    text(
                        "DELETE FROM connector_sync_attempts USING connector_sync_runs r "
                        "WHERE connector_sync_attempts.run_id = r.run_id "
                        "AND r.project_id = :project_id"
                    ),
                    {"project_id": project_id},
                ).rowcount or 0
            else:
                # Unit doubles without PostgreSQL DELETE..USING or the attempts table.
                attempts = 0
            removed += attempts
            if not is_postgresql:
                # Unit doubles carry no connector schema or purge helper; the
                # real order + helper are proved on disposable PostgreSQL.
                return removed
            dead_letters = connection.execute(
                text("DELETE FROM connector_dead_letters WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).rowcount or 0
            removed += dead_letters
            inbox = connection.execute(
                text("DELETE FROM connector_event_inbox WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).rowcount or 0
            removed += inbox
            connection.execute(
                text(
                    "UPDATE connector_sync_runs SET dead_letter_id = NULL, "
                    "retry_of_run_id = NULL WHERE project_id = :project_id"
                ),
                {"project_id": project_id},
            )
            runs = connection.execute(
                text("DELETE FROM connector_sync_runs WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).rowcount or 0
            removed += runs
            cursors = connection.execute(
                text("DELETE FROM connector_cursors WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).rowcount or 0
            removed += cursors
            audit = connection.execute(
                text("DELETE FROM connector_audit_records WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).rowcount or 0
            removed += audit
            installations = connection.execute(
                text("DELETE FROM connector_installations WHERE project_id = :project_id"),
                {"project_id": project_id},
            ).rowcount or 0
            removed += installations
            for table in ("teams_setup_handles", "github_public_issues_setup_handles"):
                cleared = connection.execute(
                    text(f"DELETE FROM {table} WHERE project_id = :project_id"),
                    {"project_id": project_id},
                ).rowcount or 0
                removed += cleared
            guarded_count = connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM review_decision_receipts WHERE project_id = :project_id) + "
                    "(SELECT count(*) FROM correction_burden_events WHERE project_id = :project_id)"
                ),
                {"project_id": project_id},
            ).scalar_one()
            if int(guarded_count) > 0:
                guarded = connection.execute(
                    text("SELECT purged_rows FROM projecta_purge_project_scope(:project_id)"),
                    {"project_id": project_id},
                ).all()
                removed += sum(int(row[0]) for row in guarded)
        return removed

    def _forget_ledger_scope(self, export_ids: set[str]) -> int:
        assert self._import_root is not None
        ledger_path = self._import_root / "ledger.json"
        if not export_ids or not ledger_path.exists():
            return 0
        ledger = _read_private_json(ledger_path)
        if set(ledger) != {"formatVersion", "imports"} or ledger.get("formatVersion") != 1:
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        imports = dict(cast(Mapping[str, object], ledger["imports"]))
        forgotten = 0
        for export_id in sorted(export_ids):
            if export_id in imports:
                del imports[export_id]
                forgotten += 1
        _write_private_json(ledger_path, {"formatVersion": 1, "imports": imports})
        return forgotten

    def _remove_memberships(self, project_id: str) -> int:
        """Remove authorization grants for the scope; global sessions untouched."""
        repository = self._identity_repository
        remover = getattr(repository, "remove_memberships_for_project", None)
        if remover is None:
            return 0
        return int(remover(project_id))

    def _publish_registry_removal(self, project_id: str) -> None:
        assert self._registry_path is not None
        registry = _read_registry(self._registry_path)
        entries = _registry_entries(registry)
        remaining = [item for item in entries if item["projectId"] != project_id]
        if len(remaining) == len(entries):
            raise ProjectDeletionFailure("DELETE_UNKNOWN_PROJECT", status_code=404)
        updated = dict(registry)
        if remaining:
            updated["projects"] = remaining
            if registry.get("projectId") == project_id:
                updated["projectId"] = remaining[0]["projectId"]
                updated["projectName"] = remaining[0]["projectName"]
        else:
            # Persisted empty catalog: no seed resurrection is possible because
            # first-run provisioning refuses to overwrite an existing file.
            updated["projects"] = []
        _write_private_json(self._registry_path, updated)
        reread = _read_registry(self._registry_path)
        if {item["projectId"] for item in _registry_entries(reread)} != {
            item["projectId"] for item in remaining
        }:
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)

    def _clear_selections(self, project_id: str) -> None:
        with self._database.read_transaction() as connection:
            try:
                rows = connection.execute(
                    "SELECT actor_id FROM project_selections WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            except Exception:
                return
            actors = [str(row["actor_id"]) for row in rows]
        for actor_id in actors:
            self._database.execute(
                "DELETE FROM project_selections WHERE actor_id = ?", (actor_id,)
            )

    def _read_ledger(self) -> Mapping[str, str]:
        assert self._import_root is not None
        path = self._import_root / "ledger.json"
        if not path.exists():
            return {}
        value = _read_private_json(path)
        if set(value) != {"formatVersion", "imports"} or value.get("formatVersion") != 1:
            raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503)
        return cast(Mapping[str, str], value["imports"])


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_archive_identity(archive: Path) -> tuple[str | None, str | None]:
    """Read (projectId, exportId) from an archive manifest without trusting it."""
    import zipfile

    try:
        if archive.is_symlink() or not archive.is_file():
            return None, None
        with zipfile.ZipFile(archive, "r") as package:
            raw = package.read("manifest.json")
        manifest = json.loads(raw.decode("utf-8", "strict"))
        project = manifest.get("project") if isinstance(manifest, dict) else None
        export_id = manifest.get("exportId") if isinstance(manifest, dict) else None
        if not isinstance(project, dict) or not isinstance(export_id, str):
            return None, None
        project_id = project.get("projectId")
        if not isinstance(project_id, str) or not _PROJECT_ID.fullmatch(project_id):
            return None, None
        try:
            import uuid as _uuid

            parsed = _uuid.UUID(export_id)
            if str(parsed) != export_id or parsed.version != 4:
                return None, None
        except ValueError:
            return None, None
        return project_id, export_id
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return None, None


def _registry_entries(registry: Mapping[str, object]) -> list[dict[str, str]]:
    raw = registry.get("projects")
    if raw is None:
        return [
            {
                "projectId": cast(str, registry["projectId"]),
                "projectName": cast(str, registry["projectName"]),
            }
        ]
    if not isinstance(raw, list):
        raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
    result: list[dict[str, str]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
        item = cast(Mapping[str, object], value)
        if set(item) != {"projectId", "projectName"}:
            raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
        project_id, project_name = item["projectId"], item["projectName"]
        if (
            not isinstance(project_id, str)
            or not _PROJECT_ID.fullmatch(project_id)
            or not isinstance(project_name, str)
            or not project_name.strip()
            or len(project_name) > 128
        ):
            raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
        result.append({"projectId": project_id, "projectName": project_name})
    if len(result) > 100:
        raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
    return result


def _read_registry(path: Path) -> Mapping[str, object]:
    value = _read_private_json(path, "DELETE_DESTINATION_INVALID")
    if (
        value.get("formatVersion") != 1
        or not isinstance(value.get("projectId"), str)
        or not isinstance(value.get("projectName"), str)
        or not isinstance(value.get("actorId"), str)
    ):
        raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
    entries = _registry_entries(value)
    if entries:
        if entries[0]["projectId"] != value["projectId"]:
            raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
        if len({item["projectId"] for item in entries}) != len(entries):
            raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
    return value


def _read_private_json(path: Path, code: str = "DELETE_RECOVERY_REQUIRED") -> dict[str, object]:
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError("not a regular file")
        value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
        if not isinstance(value, dict):
            raise ValueError("not an object")
        return {str(key): item for key, item in value.items()}
    except ProjectDeletionFailure:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise ProjectDeletionFailure(code, status_code=503) from error


def _write_private_json(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ProjectDeletionFailure("DELETE_DESTINATION_INVALID", status_code=503)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    try:
        with temporary.open("xb") as output:
            output.write(json.dumps(value, sort_keys=True).encode("utf-8") + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise ProjectDeletionFailure("DELETE_FAILED", status_code=503) from error
    try:
        json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ProjectDeletionFailure("DELETE_RECOVERY_REQUIRED", status_code=503) from error
