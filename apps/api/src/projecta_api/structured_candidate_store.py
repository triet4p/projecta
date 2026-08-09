"""Operational audit storage for pre-confirmation candidate corrections."""

from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass

from projecta_api.configuration.storage import OperationalDatabase, utc_now
from projecta_api.structured_note import StructuredCandidateEditRequest


class CandidateEditConflict(Exception):
    """The candidate edit revision or idempotency key is stale."""


@dataclass(frozen=True, slots=True)
class StoredCandidateEdit:
    edit_handle: str
    project_id: str
    candidate_handle: str
    actor_id: str
    request_id: str
    revision: int
    payload: StructuredCandidateEditRequest
    created_at: str


class StructuredCandidateEditStore:
    """Keep immutable edit records and one current revision per candidate."""

    def __init__(self, database: OperationalDatabase) -> None:
        self._database = database
        self._database.execute(
            """
            CREATE TABLE IF NOT EXISTS structured_candidate_edits (
                edit_handle TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                candidate_handle TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                request_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(project_id, candidate_handle, revision)
            )
            """
        )

    def append(
        self,
        project_id: str,
        candidate_handle: str,
        actor_id: str,
        request_id: str,
        payload: StructuredCandidateEditRequest,
    ) -> StoredCandidateEdit:
        now = utc_now()
        with self._database.transaction() as connection:
            current = connection.execute(
                """
                SELECT MAX(revision) AS revision FROM structured_candidate_edits
                WHERE project_id = ? AND candidate_handle = ?
                """,
                (project_id, candidate_handle),
            ).fetchone()
            current_revision = int(current["revision"] or 0) if current else 0
            if payload.expected_revision != current_revision + 1:
                raise CandidateEditConflict()
            handle = "edit-h-" + secrets.token_hex(10)
            connection.execute(
                """
                INSERT INTO structured_candidate_edits(
                    edit_handle, project_id, candidate_handle, actor_id, request_id,
                    revision, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    handle,
                    project_id,
                    candidate_handle,
                    actor_id,
                    request_id,
                    payload.expected_revision,
                    json.dumps(payload.model_dump(mode="json", by_alias=True), sort_keys=True),
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM structured_candidate_edits WHERE edit_handle = ?", (handle,)
            ).fetchone()
        if row is None:
            raise RuntimeError("candidate edit write did not produce a row")
        return _from_row(row)

    def latest(self, project_id: str, candidate_handle: str) -> StoredCandidateEdit | None:
        """Return the current audited correction for one project-scoped candidate."""

        row = self._database.execute(
            """
            SELECT * FROM structured_candidate_edits
            WHERE project_id = ? AND candidate_handle = ?
            ORDER BY revision DESC
            LIMIT 1
            """,
            (project_id, candidate_handle),
        ).fetchone()
        return _from_row(row) if row is not None else None


def _from_row(row: sqlite3.Row) -> StoredCandidateEdit:
    return StoredCandidateEdit(
        edit_handle=str(row["edit_handle"]),
        project_id=str(row["project_id"]),
        candidate_handle=str(row["candidate_handle"]),
        actor_id=str(row["actor_id"]),
        request_id=str(row["request_id"]),
        revision=int(row["revision"]),
        payload=StructuredCandidateEditRequest.model_validate(json.loads(str(row["payload"]))),
        created_at=str(row["created_at"]),
    )
