"""Safe, finite operational persistence errors."""


class ConnectorOperationalError(RuntimeError):
    """Base class for connector operational failures."""


class ConnectorDatabaseUnavailable(ConnectorOperationalError):
    """The connector database could not be reached."""


class IdempotencyConflict(ConnectorOperationalError):
    """An event identity was reused with a different canonical body hash."""


class RevisionConflict(ConnectorOperationalError):
    """An optimistic revision check failed."""


class TelemetryIntegrityError(ConnectorOperationalError):
    """An append-only telemetry row failed independent integrity verification."""
