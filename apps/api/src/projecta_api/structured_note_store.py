"""SQLite persistence for project-scoped structured Note drafts."""

from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from hashlib import sha256

from projecta_api.configuration.storage import OperationalDatabase, utc_now
from projecta_api.structured_note import StructuredNoteDraft


class StructuredNoteDraftNotFound(Exception):
    """The requested draft is not visible in the current project scope."""


class StructuredNoteDraftConflict(Exception):
    """The draft revision or idempotency body is stale/different."""


class StructuredNoteIdempotencyConflict(Exception):
    """An idempotency key was reused with a different draft body."""


@dataclass(frozen=True, slots=True)
class StoredStructuredNoteDraft:
    handle: str
    project_id: str
    actor_id: str
    revision: int
    draft: StructuredNoteDraft
    fingerprint: str
    idempotency_key: str
    committed_note_id: str | None
    created_at: str
    updated_at: str

    @property
    def status(self) -> str:
        return self.draft.draft_status


class StructuredNoteDraftStore:
    """Persist editable drafts with revision and idempotency guards."""

    def __init__(self, database: OperationalDatabase) -> None:
        self._database = database
        self._database.execute(
            """
            CREATE TABLE IF NOT EXISTS structured_note_drafts (
                handle TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                committed_note_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, actor_id, idempotency_key)
            )
            """
        )

    def create(
        self, project_id: str, actor_id: str, key: str, draft: StructuredNoteDraft
    ) -> tuple[StoredStructuredNoteDraft, bool]:
        """Create or replay one draft for one project/actor/idempotency key."""
        fingerprint = structured_note_draft_fingerprint(draft)
        now = utc_now()
        with self._database.transaction() as connection:
            existing = connection.execute(
                """
                SELECT * FROM structured_note_drafts
                WHERE project_id = ? AND actor_id = ? AND idempotency_key = ?
                """,
                (project_id, actor_id, key),
            ).fetchone()
            if existing is not None:
                if str(existing["fingerprint"]) != fingerprint:
                    raise StructuredNoteIdempotencyConflict()
                return _draft_from_row(existing), True
            handle = _new_handle()
            connection.execute(
                """
                INSERT INTO structured_note_drafts(
                    handle, project_id, actor_id, revision, payload, fingerprint,
                    idempotency_key, committed_note_id, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    handle,
                    project_id,
                    actor_id,
                    serialize_note_draft(draft),
                    fingerprint,
                    key,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM structured_note_drafts WHERE handle = ?", (handle,)
            ).fetchone()
        if row is None:
            raise RuntimeError("structured Note draft write did not produce a row")
        return _draft_from_row(row), False

    def get(self, project_id: str, handle: str) -> StoredStructuredNoteDraft:
        row = self._database.execute(
            "SELECT * FROM structured_note_drafts WHERE project_id = ? AND handle = ?",
            (project_id, handle),
        ).fetchone()
        if row is None:
            raise StructuredNoteDraftNotFound()
        return _draft_from_row(row)

    def list(self, project_id: str, limit: int) -> list[StoredStructuredNoteDraft]:
        rows = self._database.execute(
            """
            SELECT * FROM structured_note_drafts
            WHERE project_id = ?
            ORDER BY updated_at DESC, handle ASC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [_draft_from_row(row) for row in rows]

    def update(
        self,
        project_id: str,
        handle: str,
        expected_revision: int,
        draft: StructuredNoteDraft,
    ) -> StoredStructuredNoteDraft:
        fingerprint = structured_note_draft_fingerprint(draft)
        now = utc_now()
        with self._database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM structured_note_drafts WHERE project_id = ? AND handle = ?",
                (project_id, handle),
            ).fetchone()
            if row is None:
                raise StructuredNoteDraftNotFound()
            if int(row["revision"]) != expected_revision or row["committed_note_id"]:
                raise StructuredNoteDraftConflict()
            connection.execute(
                """
                UPDATE structured_note_drafts
                SET revision = revision + 1, payload = ?, fingerprint = ?, updated_at = ?
                WHERE project_id = ? AND handle = ? AND revision = ? AND committed_note_id IS NULL
                """,
                (serialize_note_draft(draft), fingerprint, now, project_id, handle, expected_revision),
            )
            updated = connection.execute(
                "SELECT * FROM structured_note_drafts WHERE project_id = ? AND handle = ?",
                (project_id, handle),
            ).fetchone()
        if updated is None:
            raise StructuredNoteDraftConflict()
        return _draft_from_row(updated)

    def mark_committed(
        self, project_id: str, handle: str, expected_revision: int, note_id: str
    ) -> StoredStructuredNoteDraft:
        now = utc_now()
        with self._database.transaction() as connection:
            current = connection.execute(
                "SELECT payload FROM structured_note_drafts WHERE project_id = ? AND handle = ?",
                (project_id, handle),
            ).fetchone()
            if current is None:
                raise StructuredNoteDraftNotFound()
            committed_payload = StructuredNoteDraft.model_validate(
                json.loads(str(current["payload"]))
            ).model_copy(update={"draft_status": "committed"})
            updated_count = connection.execute(
                """
                UPDATE structured_note_drafts
                SET committed_note_id = ?, payload = ?, updated_at = ?
                WHERE project_id = ? AND handle = ? AND revision = ? AND committed_note_id IS NULL
                """,
                (
                    note_id,
                    serialize_note_draft(committed_payload),
                    now,
                    project_id,
                    handle,
                    expected_revision,
                ),
            ).rowcount
            if updated_count != 1:
                row = connection.execute(
                    "SELECT * FROM structured_note_drafts WHERE project_id = ? AND handle = ?",
                    (project_id, handle),
                ).fetchone()
                if row is None:
                    raise StructuredNoteDraftNotFound()
                if row["committed_note_id"] == note_id:
                    return _draft_from_row(row)
                raise StructuredNoteDraftConflict()
            row = connection.execute(
                "SELECT * FROM structured_note_drafts WHERE project_id = ? AND handle = ?",
                (project_id, handle),
            ).fetchone()
        if row is None:
            raise RuntimeError("structured Note commit did not produce a row")
        return _draft_from_row(row)


def _new_handle() -> str:
    return "draft-h-" + secrets.token_hex(12)


def serialize_note_draft(draft: StructuredNoteDraft) -> str:
    return json.dumps(
        draft.model_dump(mode="json", by_alias=True), ensure_ascii=False, sort_keys=True
    )


def structured_note_draft_fingerprint(draft: StructuredNoteDraft) -> str:
    """Return the exact serialized fingerprint used for draft idempotency."""
    return sha256(serialize_note_draft(draft).encode("utf-8")).hexdigest()


def _draft_from_row(row: sqlite3.Row) -> StoredStructuredNoteDraft:
    return StoredStructuredNoteDraft(
        handle=str(row["handle"]),
        project_id=str(row["project_id"]),
        actor_id=str(row["actor_id"]),
        revision=int(row["revision"]),
        draft=StructuredNoteDraft.model_validate(json.loads(str(row["payload"]))),
        fingerprint=str(row["fingerprint"]),
        idempotency_key=str(row["idempotency_key"]),
        committed_note_id=(str(row["committed_note_id"]) if row["committed_note_id"] else None),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
