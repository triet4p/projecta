"""Connector operational persistence boundary."""

from projecta_api.operational.database import ConnectorDatabase
from projecta_api.operational.errors import (
    ConnectorDatabaseUnavailable,
    IdempotencyConflict,
    RevisionConflict,
)

__all__ = [
    "ConnectorDatabase",
    "ConnectorDatabaseUnavailable",
    "IdempotencyConflict",
    "RevisionConflict",
]
