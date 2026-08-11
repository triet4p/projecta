"""Connection factory for the separate PostgreSQL connector boundary."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from projecta_api.config import Settings
from projecta_api.operational.errors import ConnectorDatabaseUnavailable

_LOGGER = logging.getLogger("projecta.connector.database")


class ConnectorDatabase:
    """Create short-lived SQLAlchemy connections for connector repositories."""

    def __init__(self, settings: Settings, *, engine: Engine | None = None) -> None:
        self._engine = engine or create_engine(
            settings.connector_sync_database_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=5,
            hide_parameters=True,
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def connection(self, *, operation: str = "unclassified") -> Generator[Connection, None, None]:
        """Yield a connection and translate driver errors to a safe public error."""
        try:
            with self._engine.begin() as connection:
                yield connection
        except SQLAlchemyError as exc:
            original = getattr(exc, "orig", None)
            diagnostic = getattr(original, "diag", None)
            _LOGGER.error(
                "connector database operation failed; safe failure returned operation=%s failureType=%s sqlState=%s failureReason=%s failureColumn=%s",
                operation,
                type(exc).__name__,
                getattr(
                    original,
                    "sqlstate",
                    getattr(original, "pgcode", "unclassified"),
                ),
                getattr(diagnostic, "message_primary", "unclassified"),
                getattr(diagnostic, "column_name", "unclassified"),
            )
            raise ConnectorDatabaseUnavailable("connector database unavailable") from exc

    def check_ready(self) -> bool:
        """Run a bounded readiness query without exposing the driver error."""
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise ConnectorDatabaseUnavailable("connector database unavailable") from exc
        return True

    def dispose(self) -> None:
        self._engine.dispose()
