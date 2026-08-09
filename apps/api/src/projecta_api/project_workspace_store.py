"""Server-owned active project selection persistence."""

from dataclasses import dataclass

from projecta_api.configuration.storage import OperationalDatabase, utc_now


@dataclass(frozen=True, slots=True)
class StoredProjectSelection:
    actor_id: str
    handle: str
    project_id: str
    catalog_revision: str
    updated_at: str


class ProjectSelectionRepository:
    """Keep one validated selection per server-established actor scope."""

    def __init__(self, database: OperationalDatabase) -> None:
        self._database = database
        self._database.execute(
            """
            CREATE TABLE IF NOT EXISTS project_selections (
                actor_id TEXT PRIMARY KEY,
                handle TEXT NOT NULL,
                project_id TEXT NOT NULL,
                catalog_revision TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def get(self, actor_id: str) -> StoredProjectSelection | None:
        row = self._database.execute(
            "SELECT actor_id, handle, project_id, catalog_revision, updated_at FROM project_selections WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        if row is None:
            return None
        return StoredProjectSelection(
            actor_id=str(row["actor_id"]),
            handle=str(row["handle"]),
            project_id=str(row["project_id"]),
            catalog_revision=str(row["catalog_revision"]),
            updated_at=str(row["updated_at"]),
        )

    def replace(
        self, actor_id: str, handle: str, project_id: str, catalog_revision: str
    ) -> StoredProjectSelection:
        now = utc_now()
        with self._database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO project_selections(actor_id, handle, project_id, catalog_revision, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(actor_id) DO UPDATE SET
                    handle = excluded.handle,
                    project_id = excluded.project_id,
                    catalog_revision = excluded.catalog_revision,
                    updated_at = excluded.updated_at
                """,
                (actor_id, handle, project_id, catalog_revision, now),
            )
        selected = self.get(actor_id)
        if selected is None:
            raise RuntimeError("project selection write did not produce a row")
        return selected

    def clear(self, actor_id: str) -> None:
        self._database.execute("DELETE FROM project_selections WHERE actor_id = ?", (actor_id,))
